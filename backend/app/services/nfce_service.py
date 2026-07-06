from datetime import timedelta
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.models.models import (ItemCategoryRule, Pendencia, PendenciaType, RawEvent,
                               RawEventType, RawStatus, ReceiptItem, Source, SourceType,
                               Transaction, Transport, TxChannel, TxStatus)
from app.services.import_service import make_external_id
from app.services.parsers.nfce_parser import parse_nfce_html

ALLOWED_HOSTS = {"sat.sef.sc.gov.br"}
GENERIC_ITEM_PATTERNS = ("DIVERSOS", "GENERIC", "OUTROS", "PRODUTO", "ITEM")


async def _fetch_html(url: str) -> str:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as c:
        resp = await c.get(url)
        resp.raise_for_status()
        return resp.text


async def process_nfce(session: AsyncSession, qr_url: str, transport: Transport) -> dict:
    host = urlparse(qr_url).hostname or ""
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"host não permitido: {host}")
    user = await get_single_user(session)
    html = await _fetch_html(qr_url)
    raw = RawEvent(user_id=user.id, type=RawEventType.nfce, transport=transport, payload=html)
    session.add(raw)
    try:
        parsed = parse_nfce_html(html)
    except ValueError as e:
        raw.status = RawStatus.failed
        raw.error = str(e)
        session.add(Pendencia(user_id=user.id, type=PendenciaType.parse_failed,
                              payload={"canal": "nfce", "qr_url": qr_url}))
        await session.commit()
        return {"parsed": False, "erro": str(e)}
    tx = await _find_or_create_tx(session, user, parsed)
    raw.transaction_id = tx.id
    rules = {r.pattern: r for r in
             (await session.execute(select(ItemCategoryRule))).scalars().all()}
    genericos = 0
    for item in parsed.items:
        cat = next((r for p, r in rules.items() if p in item.description.upper()), None)
        ri = ReceiptItem(transaction_id=tx.id, description=item.description,
                         product_code=item.product_code, quantity=item.quantity,
                         unit=item.unit, unit_price=item.unit_price,
                         total_price=item.total_price,
                         category=cat.category if cat else None)
        session.add(ri)
        if cat is None and any(g in item.description.upper() for g in GENERIC_ITEM_PATTERNS):
            await session.flush()
            session.add(Pendencia(user_id=user.id, type=PendenciaType.item_generico,
                                  payload={"receipt_item_id": str(ri.id),
                                           "descricao": item.description}))
            genericos += 1
    await session.commit()
    return {"parsed": True, "itens": len(parsed.items), "genericos": genericos,
            "conciliada": tx.source_channel != TxChannel.nfce}


async def _find_or_create_tx(session, user, parsed) -> Transaction:
    center = parsed.when
    rows = (await session.execute(select(Transaction).where(
        Transaction.amount == -parsed.total,
        Transaction.date >= center - timedelta(days=1),
        Transaction.date <= center + timedelta(days=1)))).scalars().all()
    if rows:
        return rows[0]
    src = (await session.execute(select(Source).where(
        Source.type == SourceType.caixa_cartao))).scalar_one()
    tx = Transaction(user_id=user.id, source_id=src.id,
                     external_id=make_external_id("nfce", parsed.cnpj, center.isoformat(), str(parsed.total)),
                     amount=-parsed.total, date=center, raw_description=parsed.emitente,
                     source_channel=TxChannel.nfce, entity=src.entity, status=TxStatus.confirmada,
                     merchant=parsed.emitente)
    session.add(tx)
    await session.flush()
    return tx
