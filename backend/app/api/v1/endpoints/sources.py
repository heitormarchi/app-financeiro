import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import encrypt_str
from app.core.database import get_session
from app.models.models import Source, SourceType

router = APIRouter(prefix="/sources")


class PasswordBody(BaseModel):
    password: str


def _inter_cert_days_left() -> int | None:
    if not settings.inter_cert_path:
        return None
    try:
        from cryptography import x509
        with open(settings.inter_cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return (cert.not_valid_after_utc - datetime.now(timezone.utc)).days
    except (OSError, ValueError):
        return None


@router.get("")
async def list_sources(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Source))).scalars().all()
    cert_days = _inter_cert_days_left()
    return [{"id": str(s.id), "type": s.type, "entity": s.entity, "bank_name": s.bank_name,
             "has_pdf_password": s.pdf_password_encrypted is not None,
             "last_ingested_at": s.last_ingested_at,
             "balance": float(s.balance) if s.balance is not None else None,
             "balance_date": s.balance_date,
             "cert_days_left": cert_days if s.type == SourceType.inter_pj else None}
            for s in rows]


@router.put("/{source_id}/pdf-password")
async def set_pdf_password(source_id: uuid.UUID, body: PasswordBody,
                           session: AsyncSession = Depends(get_session)):
    src = await session.get(Source, source_id)
    if src is None:
        raise HTTPException(404)
    src.pdf_password_encrypted = encrypt_str(body.password)
    await session.commit()
    return {"ok": True}
