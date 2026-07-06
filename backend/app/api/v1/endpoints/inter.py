from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services.inter_service import sync_inter

router = APIRouter(prefix="/inter")


@router.post("/sync")
async def trigger_sync(session: AsyncSession = Depends(get_session)):
    report = await sync_inter(session)
    return {"novas": report.novas, "duplicadas": report.duplicadas, "futuros": report.futuros}
