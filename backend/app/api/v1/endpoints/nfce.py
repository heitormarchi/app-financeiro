import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.models.models import ItemCategoryRule, Pendencia, PendenciaType, ReceiptItem, Transport
from app.services.nfce_service import process_nfce

router = APIRouter(prefix="/nfce")


class ScanBody(BaseModel):
    qr_url: str


class CategoryBody(BaseModel):
    category: str
    subcategory: str | None = None
    salvar_regra: bool = False


@router.post("/scan")
async def scan_nfce(body: ScanBody, session: AsyncSession = Depends(get_session)):
    try:
        return await process_nfce(session, body.qr_url, Transport.upload)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.put("/items/{item_id}/category")
async def set_item_category(item_id: uuid.UUID, body: CategoryBody,
                            session: AsyncSession = Depends(get_session)):
    item = await session.get(ReceiptItem, item_id)
    if item is None:
        raise HTTPException(404)
    item.category = body.category
    if body.salvar_regra:
        pattern = item.description.upper()
        rule = (await session.execute(select(ItemCategoryRule).where(
            ItemCategoryRule.pattern == pattern))).scalar_one_or_none()
        if rule is None:
            session.add(ItemCategoryRule(pattern=pattern, category=body.category,
                                         subcategory=body.subcategory))
        else:
            rule.category = body.category
            rule.subcategory = body.subcategory
    pendencias = (await session.execute(select(Pendencia).where(
        Pendencia.type == PendenciaType.item_generico,
        Pendencia.resolved == False))).scalars().all()  # noqa: E712
    for p in pendencias:
        if p.payload.get("receipt_item_id") == str(item_id):
            p.resolved = True
    await session.commit()
    return {"ok": True}
