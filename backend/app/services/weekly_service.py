from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Entity, Transaction, WeeklySummary
from app.services.insight_service import generate_weekly_summary
from app.services.push_service import send_push


async def _spend_and_categories(session: AsyncSession, entity: Entity,
                                start: date, end: date) -> tuple[float, dict[str, float]]:
    filters = (Transaction.amount < 0, Transaction.is_invoice_payment.is_(False),
              Transaction.entity == entity, Transaction.date >= start, Transaction.date < end)
    total = (await session.execute(
        select(func.sum(Transaction.amount)).where(*filters))).scalar() or 0
    rows = (await session.execute(
        select(Transaction.category, func.sum(Transaction.amount))
        .where(*filters).group_by(Transaction.category))).all()
    por_categoria = {(c or "Sem categoria"): abs(float(t)) for c, t in rows}
    return abs(float(total)), por_categoria


async def compute_week_aggregates(session: AsyncSession, entity: Entity, week_start: date) -> dict:
    week_end = week_start + timedelta(days=7)
    total, por_categoria = await _spend_and_categories(session, entity, week_start, week_end)

    media_start = week_start - timedelta(days=28)
    media_total, _ = await _spend_and_categories(session, entity, media_start, week_start)
    vs_media_30d = media_total / 4

    return {"total": total, "por_categoria": por_categoria, "vs_media_30d": vs_media_30d}


async def run_weekly_job(session: AsyncSession) -> None:
    today = date.today()
    week_start = today - timedelta(days=today.weekday() + 1 if today.weekday() != 6 else 0)

    entities_com_tx = (await session.execute(
        select(Transaction.entity).where(
            Transaction.date >= week_start,
            Transaction.date < week_start + timedelta(days=7)).distinct())).scalars().all()

    for entity in entities_com_tx:
        agg = await compute_week_aggregates(session, entity, week_start)
        if agg["total"] == 0:
            continue
        texto = await generate_weekly_summary(agg)
        session.add(WeeklySummary(user_id=(await _user_id(session)), week_start=week_start,
                                  entity=entity, text=texto))
        await session.commit()
        await send_push(session, "Resumo da semana", texto[:180])


async def _user_id(session: AsyncSession):
    from app.core.auth import get_single_user
    user = await get_single_user(session)
    return user.id
