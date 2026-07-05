import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.models.models import CollectivePattern, Entity, EnrichmentSource, Transaction

router = APIRouter()


class CategoryBody(BaseModel):
    category: str
    subcategory: str | None = None


@router.get("/transactions")
async def list_transactions(month: str | None = None, category: str | None = None,
                            source_id: uuid.UUID | None = None, entity: str | None = None,
                            limit: int = 50, offset: int = 0,
                            session: AsyncSession = Depends(get_session)):
    stmt = select(Transaction).options(selectinload(Transaction.receipt_items))
    if month:
        year, mo = (int(p) for p in month.split("-"))
        start = date(year, mo, 1)
        end = date(year + 1, 1, 1) if mo == 12 else date(year, mo + 1, 1)
        stmt = stmt.where(Transaction.date >= start, Transaction.date < end)
    if category:
        stmt = stmt.where(Transaction.category == category)
    if source_id:
        stmt = stmt.where(Transaction.source_id == source_id)
    if entity and entity != "todas":
        stmt = stmt.where(Transaction.entity == Entity(entity))
    stmt = stmt.order_by(Transaction.date.desc()).limit(limit).offset(offset)
    txs = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": str(t.id), "amount": float(t.amount), "date": t.date,
            "raw_description": t.raw_description, "merchant": t.merchant,
            "category": t.category, "subcategory": t.subcategory,
            "entity": t.entity, "status": t.status, "source_channel": t.source_channel,
            "is_invoice_payment": t.is_invoice_payment,
            "installment_no": t.installment_no, "installment_total": t.installment_total,
            "receipt_items": [
                {"id": str(i.id), "description": i.description, "total_price": float(i.total_price),
                 "category": i.category}
                for i in t.receipt_items
            ],
        }
        for t in txs
    ]


@router.patch("/transactions/{transaction_id}")
async def update_transaction_category(transaction_id: uuid.UUID, body: CategoryBody,
                                      session: AsyncSession = Depends(get_session)):
    tx = await session.get(Transaction, transaction_id)
    if tx is None:
        raise HTTPException(404)
    tx.category = body.category
    tx.subcategory = body.subcategory
    tx.enrichment_source = EnrichmentSource.user

    pattern = tx.raw_description.upper()[:80]
    rule = (await session.execute(select(CollectivePattern).where(
        CollectivePattern.raw_pattern == pattern))).scalar_one_or_none()
    if rule is None:
        session.add(CollectivePattern(raw_pattern=pattern, merchant=tx.merchant or pattern,
                                      category=body.category, subcategory=body.subcategory,
                                      confidence=1.0))
    else:
        rule.category = body.category
        rule.subcategory = body.subcategory

    await session.commit()
    return {"ok": True}
