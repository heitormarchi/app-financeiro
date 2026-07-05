import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.core.database import get_session
from app.models.models import Pendencia, PendenciaType, Source, Transport
from app.services.import_service import import_fatura, import_ofx
from app.services.parsers.fatura_parser import PdfPasswordError

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


@router.post("/fatura")
async def upload_fatura(source_id: uuid.UUID, file: UploadFile,
                        session: AsyncSession = Depends(get_session)):
    src = await _get_source(source_id, session)
    content = await file.read()
    try:
        report = await import_fatura(session, src, content, Transport.upload)
    except PdfPasswordError as exc:
        user = await get_single_user(session)
        session.add(Pendencia(user_id=user.id, type=PendenciaType.parse_failed,
                              payload={"source_id": str(source_id), "erro": str(exc)}))
        await session.commit()
        raise HTTPException(422, str(exc))
    return report
