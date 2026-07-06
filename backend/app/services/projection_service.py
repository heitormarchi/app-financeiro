from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import (Entity, RecurringRule, ScheduledStatus, ScheduledTransaction, Source,
                               Transaction, TransferSuggestion)
from app.services.date_utils import add_months
from app.services.push_service import send_push


async def compute_projection(session, days: int = 30) -> dict:
    sources = (await session.execute(select(Source))).scalars().all()
    scheduled = (await session.execute(select(ScheduledTransaction).where(
        ScheduledTransaction.status == ScheduledStatus.previsto))).scalars().all()
    today = date.today()
    result: dict = {}
    for src in sources:
        base_desconhecido = src.balance is None
        saldo = src.balance if src.balance is not None else Decimal("0")
        deltas: dict[date, Decimal] = {}
        for s in scheduled:
            if s.source_id == src.id:
                deltas[s.due_date] = deltas.get(s.due_date, Decimal("0")) + s.amount
        series = []
        for i in range(days):
            d = today + timedelta(days=i)
            saldo += deltas.get(d, Decimal("0"))
            entry = {"date": d.isoformat(), "saldo_projetado": float(saldo)}
            if base_desconhecido:
                entry["saldo_base_desconhecido"] = True
            series.append(entry)
        result[str(src.id)] = series
    return result


def _round_up_100(v: Decimal) -> Decimal:
    return (v / 100).to_integral_value(rounding=ROUND_CEILING) * 100


async def detect_low_balance(session) -> list[TransferSuggestion]:
    user = await get_single_user(session)
    proj = await compute_projection(session, days=30)
    sources = {str(s.id): s for s in (await session.execute(select(Source))).scalars().all()}
    empresa_fonte = next((s for s in sources.values()
                          if s.entity == Entity.empresa and s.balance), None)
    week_start = date.today() - timedelta(days=date.today().weekday())
    existing_this_week = (await session.execute(select(TransferSuggestion).where(
        TransferSuggestion.status == "sugerida",
        TransferSuggestion.suggested_at >= datetime.combine(week_start, time.min, tzinfo=timezone.utc),
    ))).scalars().first()
    created: list[TransferSuggestion] = []
    for sid, series in proj.items():
        src = sources[sid]
        if src.entity != Entity.pessoal or empresa_fonte is None or existing_this_week:
            continue
        threshold = src.low_balance_threshold or Decimal("0")
        negativos = [p for p in series if Decimal(str(p["saldo_projetado"])) < threshold]
        if not negativos:
            continue
        primeiro = negativos[0]
        min_saldo = min(Decimal(str(p["saldo_projetado"])) for p in negativos)
        valor = _round_up_100(abs(min_saldo))
        causas = (await session.execute(select(ScheduledTransaction).where(
            ScheduledTransaction.source_id == src.id,
            ScheduledTransaction.status == ScheduledStatus.previsto,
        ).order_by(ScheduledTransaction.due_date.asc()))).scalars().all()
        descs = ", ".join(c.description for c in causas[:3])
        reason = (f"Saldo {src.bank_name} ficará negativo em {primeiro['date']} "
                 f"(motivos: {descs})")
        sug = TransferSuggestion(user_id=user.id, amount=valor, reason=reason)
        session.add(sug)
        created.append(sug)
    await session.commit()
    return created


async def reconcile_scheduled(session) -> None:
    previstos = (await session.execute(select(ScheduledTransaction).where(
        ScheduledTransaction.status == ScheduledStatus.previsto))).scalars().all()
    for sched in previstos:
        due_dt = datetime(sched.due_date.year, sched.due_date.month, sched.due_date.day, tzinfo=timezone.utc)
        match = (await session.execute(select(Transaction).where(
            Transaction.amount >= sched.amount - Decimal("0.01"),
            Transaction.amount <= sched.amount + Decimal("0.01"),
            Transaction.date >= due_dt - timedelta(days=2),
            Transaction.date <= due_dt + timedelta(days=2),
        ))).scalars().first()
        if match is not None:
            sched.status = ScheduledStatus.efetivado
            sched.transaction_id = match.id
    await session.commit()


async def run_projection_job(session) -> None:
    from app.services.recurring_service import materialize_recurring
    await materialize_recurring(session)
    await reconcile_scheduled(session)
    for sug in await detect_low_balance(session):
        await send_push(session, "Saldo baixo previsto", sug.reason)


async def project_future_installments(session, entity: str | None = None) -> list[dict]:
    """Projeta as parcelas restantes de compras já parceladas no cartão, a partir das
    transações já importadas (installment_no/installment_total) — nenhum dado novo é
    necessário, a fatura do cartão já informa a parcela e o total em cada linha."""
    stmt = select(Transaction).where(
        Transaction.installment_total.is_not(None),
        Transaction.installment_no < Transaction.installment_total,
    )
    if entity and entity != "todas":
        stmt = stmt.where(Transaction.entity == Entity(entity))
    txs = (await session.execute(stmt)).scalars().all()

    latest: dict[tuple, Transaction] = {}
    for t in txs:
        key = (t.source_id, t.original_purchase_date, t.installment_total, t.merchant or t.raw_description)
        cur = latest.get(key)
        if cur is None or (t.installment_no or 0) > (cur.installment_no or 0):
            latest[key] = t

    result = []
    for (source_id, _orig_date, total, desc), t in latest.items():
        restantes = total - t.installment_no
        base = t.date.date() if isinstance(t.date, datetime) else t.date
        parcelas = [
            {"competencia": add_months(base, i).strftime("%Y-%m"), "numero": t.installment_no + i,
             "valor": abs(float(t.amount))}
            for i in range(1, restantes + 1)
        ]
        result.append({
            "descricao": desc, "source_id": str(source_id) if source_id else None,
            "entity": t.entity, "installment_no_atual": t.installment_no,
            "installment_total": total, "valor_parcela": abs(float(t.amount)),
            "parcelas_restantes": parcelas,
        })
    result.sort(key=lambda r: r["descricao"])
    return result


async def compute_monthly_cashflow(session, months: int = 6, entity: str | None = None) -> list[dict]:
    """Agrega, mês a mês, os lançamentos futuros conhecidos: scheduled_transactions
    (automáticos + manuais/recorrentes) e as parcelas de cartão ainda restantes."""
    ent = Entity(entity) if entity and entity != "todas" else None

    scheduled = (await session.execute(select(ScheduledTransaction).where(
        ScheduledTransaction.status == ScheduledStatus.previsto))).scalars().all()
    sources = {s.id: s for s in (await session.execute(select(Source))).scalars().all()}
    rules = {r.id: r for r in (await session.execute(select(RecurringRule))).scalars().all()}

    today = date.today()
    buckets: dict[str, Decimal] = {
        add_months(date(today.year, today.month, 1), i).strftime("%Y-%m"): Decimal("0")
        for i in range(months)
    }

    for s in scheduled:
        if ent is not None:
            rule = rules.get(s.recurring_rule_id) if s.recurring_rule_id else None
            src = sources.get(s.source_id) if s.source_id else None
            item_entity = rule.entity if rule else (src.entity if src else None)
            if item_entity != ent:
                continue
        key = s.due_date.strftime("%Y-%m")
        if key in buckets:
            buckets[key] += s.amount

    for item in await project_future_installments(session, entity=entity):
        for p in item["parcelas_restantes"]:
            if p["competencia"] in buckets:
                buckets[p["competencia"]] -= Decimal(str(p["valor"]))

    return [{"month": m, "total": float(v)} for m, v in buckets.items()]
