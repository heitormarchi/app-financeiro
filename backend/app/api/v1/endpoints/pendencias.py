import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.core.database import get_session
from app.models.models import (CollectivePattern, EnrichmentSource, ItemCategoryRule,
                               Pendencia, PendenciaType, RawEvent, RawStatus, ReceiptItem,
                               Source, SourceType, Transaction, TxChannel, TxStatus)
from app.services.import_service import enrich_and_fill, make_external_id
from app.services.parsers.sms_parser import parse_caixa_sms

router = APIRouter(prefix="/pendencias")


class ResolveBody(BaseModel):
    descricao: str | None = None
    category: str | None = None
    subcategory: str | None = None


@router.get("")
async def list_pendencias(resolved: bool = False, session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Pendencia).where(
        Pendencia.resolved == resolved))).scalars().all()
    return [{"id": str(p.id), "type": p.type, "payload": p.payload, "resolved": p.resolved,
             "created_at": p.created_at} for p in rows]


@router.post("/{pendencia_id}/resolve")
async def resolve_pendencia(pendencia_id: uuid.UUID, body: ResolveBody,
                            session: AsyncSession = Depends(get_session)):
    p = await session.get(Pendencia, pendencia_id)
    if p is None:
        raise HTTPException(404)

    receipt_item_id = p.payload.get("receipt_item_id")
    transaction_id = p.payload.get("transaction_id")

    if receipt_item_id and body.category:
        item = await session.get(ReceiptItem, uuid.UUID(receipt_item_id))
        if item is not None:
            item.category = body.category
            pattern = item.description.upper()
            rule = (await session.execute(select(ItemCategoryRule).where(
                ItemCategoryRule.pattern == pattern))).scalar_one_or_none()
            if rule is None:
                session.add(ItemCategoryRule(pattern=pattern, category=body.category,
                                             subcategory=body.subcategory))
            else:
                rule.category = body.category
                rule.subcategory = body.subcategory

    if transaction_id:
        tx = await session.get(Transaction, uuid.UUID(transaction_id))
        if tx is not None:
            if body.descricao:
                tx.merchant = body.descricao
                tx.enrichment_source = EnrichmentSource.user
            if body.category:
                tx.category = body.category
                tx.subcategory = body.subcategory
                tx.enrichment_source = EnrichmentSource.user
            if body.descricao or body.category:
                pattern = tx.raw_description.upper()[:80]
                rule = (await session.execute(select(CollectivePattern).where(
                    CollectivePattern.raw_pattern == pattern))).scalar_one_or_none()
                if rule is None:
                    session.add(CollectivePattern(
                        raw_pattern=pattern, merchant=body.descricao or tx.merchant or pattern,
                        category=body.category or tx.category or "?",
                        subcategory=body.subcategory or tx.subcategory, confidence=1.0))
                else:
                    if body.descricao:
                        rule.merchant = body.descricao
                    if body.category:
                        rule.category = body.category
                        rule.subcategory = body.subcategory

    p.resolved = True
    await session.commit()
    return {"ok": True}


@router.post("/{pendencia_id}/reprocess")
async def reprocess_pendencia(pendencia_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    p = await session.get(Pendencia, pendencia_id)
    if p is None:
        raise HTTPException(404)
    if p.type != PendenciaType.parse_failed or p.payload.get("canal") != "sms":
        raise HTTPException(422, "pendência não é reprocessável")

    raw_event_id = p.payload.get("raw_event_id")
    raw = await session.get(RawEvent, uuid.UUID(raw_event_id)) if raw_event_id else None
    if raw is None:
        raise HTTPException(404, "raw_event não encontrado")

    parsed = parse_caixa_sms(raw.payload, year=raw.created_at.year if raw.created_at else None)
    if parsed is None:
        raise HTTPException(422, "SMS ainda não reconhecido")

    user = await get_single_user(session)
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
        await session.flush()
        raw.transaction_id = tx.id

    raw.status = RawStatus.parsed
    raw.error = None
    p.resolved = True
    await session.commit()
    return {"ok": True, "novo": dup is None}
