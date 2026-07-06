from sqlalchemy import select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import ScheduledStatus, ScheduledTransaction
from app.services.projection_service import (compute_monthly_cashflow, compute_projection,
                                             project_future_installments)

router = APIRouter(prefix="/scheduled")


@router.get("")
async def list_scheduled(status: str = "previsto", session: AsyncSession = Depends(get_session)):
    stmt = select(ScheduledTransaction).where(
        ScheduledTransaction.status == ScheduledStatus(status)
    ).order_by(ScheduledTransaction.due_date.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {"id": str(s.id), "due_date": s.due_date, "description": s.description,
         "amount": float(s.amount), "origin": s.origin, "status": s.status,
         "recurring_rule_id": str(s.recurring_rule_id) if s.recurring_rule_id else None}
        for s in rows
    ]


@router.get("/projection")
async def get_projection(days: int = 30, session: AsyncSession = Depends(get_session)):
    return await compute_projection(session, days=days)


@router.get("/parcelas-futuras")
async def get_parcelas_futuras(entity: str | None = None, session: AsyncSession = Depends(get_session)):
    return await project_future_installments(session, entity=entity)


@router.get("/cashflow")
async def get_cashflow(months: int = 6, entity: str | None = None,
                       session: AsyncSession = Depends(get_session)):
    return await compute_monthly_cashflow(session, months=months, entity=entity)
