import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import encrypt_str
from app.core.database import get_session
from app.models.models import Source

router = APIRouter(prefix="/sources")


class PasswordBody(BaseModel):
    password: str


@router.get("")
async def list_sources(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Source))).scalars().all()
    return [{"id": str(s.id), "type": s.type, "entity": s.entity, "bank_name": s.bank_name,
             "has_pdf_password": s.pdf_password_encrypted is not None,
             "last_ingested_at": s.last_ingested_at} for s in rows]


@router.put("/{source_id}/pdf-password")
async def set_pdf_password(source_id: uuid.UUID, body: PasswordBody,
                           session: AsyncSession = Depends(get_session)):
    src = await session.get(Source, source_id)
    if src is None:
        raise HTTPException(404)
    src.pdf_password_encrypted = encrypt_str(body.password)
    await session.commit()
    return {"ok": True}
