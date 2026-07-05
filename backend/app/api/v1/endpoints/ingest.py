from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.core.database import get_session
from app.models.models import (Pendencia, PendenciaType, RawEvent, RawEventType, RawStatus,
                               Source, SourceType, Transaction, Transport, TxChannel, TxStatus)
from app.services.import_service import enrich_and_fill, make_external_id
from app.services.parsers.sms_parser import parse_caixa_sms

router = APIRouter(prefix="/ingest")


class SmsBody(BaseModel):
    text: str
    received_at: datetime


@router.post("/sms")
async def ingest_sms(body: SmsBody, response: Response,
                     session: AsyncSession = Depends(get_session)):
    user = await get_single_user(session)
    raw = RawEvent(user_id=user.id, type=RawEventType.sms, transport=Transport.atalho,
                   payload=body.text)
    session.add(raw)
    parsed = parse_caixa_sms(body.text, year=body.received_at.year)
    if parsed is None:
        raw.status = RawStatus.failed
        raw.error = "formato de SMS não reconhecido"
        session.add(Pendencia(user_id=user.id, type=PendenciaType.parse_failed,
                              payload={"canal": "sms", "texto": body.text}))
        await session.commit()
        response.status_code = 202
        return {"parsed": False}
    src = (await session.execute(select(Source).where(
        Source.type == SourceType.caixa_cartao))).scalar_one()
    ext = make_external_id("sms", parsed.when.isoformat(), str(parsed.amount), parsed.merchant)
    dup = (await session.execute(select(Transaction).where(
        Transaction.source_id == src.id, Transaction.external_id == ext))).scalar_one_or_none()
    if dup is None:
        tx = Transaction(user_id=user.id, source_id=src.id, external_id=ext,
                         amount=-parsed.amount, date=parsed.when,
                         raw_description=parsed.merchant, source_channel=TxChannel.sms,
                         entity=src.entity, status=TxStatus.provisoria)
        await enrich_and_fill(tx)
        session.add(tx)
        raw.transaction_id = tx.id
    await session.commit()
    return {"parsed": True, "novo": dup is None}
