from datetime import datetime, timezone
from decimal import Decimal

from app.core.auth import get_single_user
from app.models.models import Entity, Source, SourceType, Transaction, TxChannel, TxStatus


async def test_criar_transacao_completa(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal, bank_name="Cartão Caixa")
    session.add(src)
    await session.flush()
    tx = Transaction(
        user_id=user.id, source_id=src.id, external_id="abc123",
        amount=Decimal("-87.50"), date=datetime(2026, 7, 4, tzinfo=timezone.utc),
        raw_description="PADARIA XYZ", source_channel=TxChannel.sms,
        entity=Entity.pessoal, status=TxStatus.provisoria,
    )
    session.add(tx)
    await session.flush()
    assert tx.is_invoice_payment is False and tx.installment_no is None
