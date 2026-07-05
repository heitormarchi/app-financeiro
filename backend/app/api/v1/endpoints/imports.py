import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import Source, Transport
from app.services.import_service import import_ofx

router = APIRouter(prefix="/imports")


async def _get_source(source_id: uuid.UUID, session: AsyncSession) -> Source:
    src = await session.get(Source, source_id)
    if src is None:
        raise HTTPException(404, "fonte não encontrada")
    return src


@router.post("/ofx")
async def upload_ofx(source_id: uuid.UUID, file: UploadFile,
                     session: AsyncSession = Depends(get_session)):
    src = await _get_source(source_id, session)
    report = await import_ofx(session, src, await file.read(), Transport.upload)
    return report
