from decimal import Decimal
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import Entity, Source, SourceType, Transaction, TxChannel
from app.services.inter_service import sync_inter

EXTRATO = [{"idTransacao": "i-1", "dataEntrada": "2026-07-01", "valor": "-350.00",
            "descricao": "PIX ENVIADO FORNECEDOR X", "tipoOperacao": "D"},
           {"idTransacao": "i-2", "dataEntrada": "2026-07-02", "valor": "1200.00",
            "descricao": "PIX RECEBIDO CLIENTE Y", "tipoOperacao": "C"}]


async def test_sync_cria_transacoes_empresa(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.inter_pj, entity=Entity.empresa,
                 bank_name="Inter Empresas")
    session.add(src); await session.commit()
    with patch("app.services.inter_service.InterClient") as MockClient:
        inst = MockClient.return_value
        inst.get_extrato = AsyncMock(return_value=EXTRATO)
        inst.get_saldo = AsyncMock(return_value=Decimal("8500.00"))
        inst.get_pagamentos_agendados = AsyncMock(return_value=[])
        r = await sync_inter(session)
    assert r.novas == 2
    txs = (await session.execute(select(Transaction))).scalars().all()
    assert all(t.entity == Entity.empresa and t.source_channel == TxChannel.inter for t in txs)
    await session.refresh(src)
    assert float(src.balance) == 8500.00
    # reimport não duplica
    with patch("app.services.inter_service.InterClient") as MockClient:
        inst = MockClient.return_value
        inst.get_extrato = AsyncMock(return_value=EXTRATO)
        inst.get_saldo = AsyncMock(return_value=Decimal("8500.00"))
        inst.get_pagamentos_agendados = AsyncMock(return_value=[])
        r2 = await sync_inter(session)
    assert r2.novas == 0
