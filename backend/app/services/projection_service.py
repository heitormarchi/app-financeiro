from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import (Entity, ScheduledStatus, ScheduledTransaction, Source,
                               Transaction, TransferSuggestion)
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
    await reconcile_scheduled(session)
    for sug in await detect_low_balance(session):
        await send_push(session, "Saldo baixo previsto", sug.reason)
