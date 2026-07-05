from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Entity, Transaction, WeeklySummary

router = APIRouter(prefix="/dashboard")


def _month_bounds(month: str) -> tuple[date, date]:
    year, mo = (int(p) for p in month.split("-"))
    start = date(year, mo, 1)
    end = date(year + 1, 1, 1) if mo == 12 else date(year, mo + 1, 1)
    return start, end


def _add_entity_filter(stmt, entity: str | None):
    if entity and entity != "todas":
        stmt = stmt.where(Transaction.entity == Entity(entity))
    return stmt


@router.get("/summary")
async def dashboard_summary(month: str, entity: str | None = None,
                            session: AsyncSession = Depends(get_session)):
    start, end = _month_bounds(month)
    base_filters = (Transaction.amount < 0, Transaction.is_invoice_payment.is_(False),
                    Transaction.date >= start, Transaction.date < end)

    total_stmt = _add_entity_filter(select(func.sum(Transaction.amount)).where(*base_filters), entity)
    total_gasto = (await session.execute(total_stmt)).scalar() or 0

    cat_stmt = _add_entity_filter(
        select(Transaction.category, func.sum(Transaction.amount))
        .where(*base_filters).group_by(Transaction.category), entity)
    total_por_categoria = [
        {"category": c, "total": abs(float(t))}
        for c, t in (await session.execute(cat_stmt)).all()
    ]

    evolucao = []
    y, mo = start.year, start.month
    for _ in range(6):
        m_start = date(y, mo, 1)
        m_end = date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)
        m_stmt = _add_entity_filter(
            select(func.sum(Transaction.amount)).where(
                Transaction.amount < 0, Transaction.is_invoice_payment.is_(False),
                Transaction.date >= m_start, Transaction.date < m_end), entity)
        m_total = (await session.execute(m_stmt)).scalar() or 0
        evolucao.append({"month": m_start.strftime("%Y-%m"), "total": abs(float(m_total))})
        mo -= 1
        if mo == 0:
            mo, y = 12, y - 1
    evolucao.reverse()

    top5_stmt = _add_entity_filter(
        select(Transaction).where(*base_filters).order_by(Transaction.amount.asc()).limit(5), entity)
    top5 = [
        {"descricao": t.merchant or t.raw_description, "valor": abs(float(t.amount)), "data": t.date}
        for t in (await session.execute(top5_stmt)).scalars().all()
    ]

    resumo_stmt = select(WeeklySummary).order_by(WeeklySummary.week_start.desc()).limit(1)
    if entity and entity != "todas":
        resumo_stmt = resumo_stmt.where(WeeklySummary.entity == Entity(entity))
    resumo_semanal = (await session.execute(resumo_stmt)).scalars().first()

    return {
        "total_gasto": abs(float(total_gasto)),
        "total_por_categoria": total_por_categoria,
        "evolucao": evolucao,
        "top5": top5,
        "resumo_semanal": resumo_semanal.text if resumo_semanal else None,
    }
