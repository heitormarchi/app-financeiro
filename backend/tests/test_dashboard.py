from datetime import datetime, timezone
from decimal import Decimal

from app.core.auth import get_single_user
from app.models.models import Entity, Source, SourceType, Transaction, TxChannel, TxStatus


async def _tx(session, src, user, amount, desc, category=None, invoice=False, month=7):
    tx = Transaction(user_id=user.id, source_id=src.id,
                     external_id=f"e-{desc}-{amount}", amount=Decimal(amount),
                     date=datetime(2026, month, 10, tzinfo=timezone.utc),
                     raw_description=desc, source_channel=TxChannel.ofx,
                     entity=Entity.pessoal, status=TxStatus.confirmada,
                     category=category, is_invoice_payment=invoice)
    session.add(tx)
    await session.flush()
    return tx


async def test_summary_exclui_pagamento_fatura(client, session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB")
    session.add(src); await session.flush()
    await _tx(session, src, user, "-100.00", "MERCADO A", category="Mercado")
    await _tx(session, src, user, "-5000.00", "PAG FATURA CARTAO", invoice=True)
    await session.commit()
    r = await client.get("/api/v1/dashboard/summary?month=2026-07&entity=pessoal")
    assert r.status_code == 200
    assert float(r.json()["total_gasto"]) == 100.00


async def test_evolucao_aceita_months_param(client, session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB")
    session.add(src); await session.flush()
    await _tx(session, src, user, "-100.00", "MERCADO A", category="Mercado")
    await session.commit()
    r = await client.get("/api/v1/dashboard/summary?month=2026-07&entity=pessoal&months=12")
    assert r.status_code == 200
    assert len(r.json()["evolucao"]) == 12


async def test_patch_categoria(client, session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB")
    session.add(src); await session.flush()
    tx = await _tx(session, src, user, "-50.00", "LOJA MISTERIOSA")
    await session.commit()
    r = await client.patch(f"/api/v1/transactions/{tx.id}",
                           json={"category": "Vestuário", "subcategory": None})
    assert r.status_code == 200
    await session.refresh(tx)
    assert tx.category == "Vestuário" and tx.enrichment_source == "user"
