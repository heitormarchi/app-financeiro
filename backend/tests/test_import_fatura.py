from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import (Entity, Source, SourceType,
                               Transaction, TxChannel, TxStatus)
from app.services.import_service import import_fatura
from app.models.models import Transport

TEXT = (Path(__file__).parent / "fixtures" / "fatura_texto_anon.txt").read_text(encoding="utf-8")


async def _cartao(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.caixa_cartao, entity=Entity.pessoal,
                 bank_name="Cartão Caixa")
    session.add(src)
    await session.flush()
    return user, src


async def test_fatura_cria_transacoes(session):
    user, src = await _cartao(session)
    report = await import_fatura(session, src, TEXT, Transport.upload, pre_extracted=True)
    assert report.novas > 0 and report.duplicadas == 0
    report2 = await import_fatura(session, src, TEXT, Transport.upload, pre_extracted=True)
    assert report2.novas == 0


async def test_concilia_sms_provisoria(session):
    user, src = await _cartao(session)
    # SMS anterior: mesma data/valor de uma linha conhecida da fixture (118,54 em 05/06)
    sms_tx = Transaction(user_id=user.id, source_id=src.id, external_id="sms-1",
                         amount=Decimal("-118.54"),
                         date=datetime(2026, 6, 5, tzinfo=timezone.utc),
                         raw_description="BISTEK", source_channel=TxChannel.sms,
                         entity=Entity.pessoal, status=TxStatus.provisoria)
    session.add(sms_tx)
    await session.flush()
    before = (await session.execute(select(Transaction))).scalars().all()
    await import_fatura(session, src, TEXT, Transport.upload, pre_extracted=True)
    await session.refresh(sms_tx)
    assert sms_tx.status == TxStatus.confirmada  # confirmada, não duplicada
    txs = (await session.execute(select(Transaction).where(
        Transaction.amount == Decimal("-118.54")))).scalars().all()
    assert len(txs) == 1
