from sqlalchemy import select
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import ScheduledStatus, ScheduledTransaction

router = APIRouter(prefix="/scheduled")


@router.get("")
async def list_scheduled(status: str = "previsto", session: AsyncSession = Depends(get_session)):
    stmt = select(ScheduledTransaction).where(
        ScheduledTransaction.status == ScheduledStatus(status)
    ).order_by(ScheduledTransaction.due_date.asc())
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {"id": str(s.id), "due_date": s.due_date, "description": s.description,
         "amount": float(s.amount), "origin": s.origin, "status": s.status}
        for s in rows
    ]
