import uuid
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.models import TransferSuggestion
from app.services.inter_service import InterClient

router = APIRouter(prefix="/transfers")

MAX_AMOUNT = Decimal("5000")  # teto de sanidade — evita erro de digitação virar transferência grande


class ConfirmBody(BaseModel):
    amount: str


@router.get("")
async def list_transfers(status: str = "sugerida", session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(TransferSuggestion).where(
        TransferSuggestion.status == status).order_by(
        TransferSuggestion.suggested_at.desc()))).scalars().all()
    return [{"id": str(t.id), "amount": float(t.amount), "reason": t.reason,
             "status": t.status, "pix_id": t.pix_id, "suggested_at": t.suggested_at}
            for t in rows]


@router.post("/{transfer_id}/confirm")
async def confirm_transfer(transfer_id: uuid.UUID, body: ConfirmBody,
                           session: AsyncSession = Depends(get_session)):
    s = await session.get(TransferSuggestion, transfer_id)
    if s is None or s.status != "sugerida":
        raise HTTPException(404)
    try:
        amount = Decimal(body.amount)
    except InvalidOperation:
        raise HTTPException(422, "amount inválido")
    if amount <= 0 or amount > MAX_AMOUNT:
        raise HTTPException(422, f"amount deve ser > 0 e <= {MAX_AMOUNT}")
    client = InterClient()
    try:
        pix_id = await client.send_pix(amount, settings.inter_pix_dest_key, s.reason)
    except Exception as e:
        raise HTTPException(502, f"Pix falhou — faça manualmente no app do Inter ({e})")
    s.status = "executada"
    s.pix_id = pix_id
    await session.commit()
    return {"ok": True, "pix_id": pix_id}


@router.post("/{transfer_id}/dismiss")
async def dismiss_transfer(transfer_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    s = await session.get(TransferSuggestion, transfer_id)
    if s is None:
        raise HTTPException(404)
    s.status = "recusada"
    await session.commit()
    return {"ok": True}
