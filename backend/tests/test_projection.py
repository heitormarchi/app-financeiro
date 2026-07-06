from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import (Entity, ScheduledOrigin, ScheduledStatus, ScheduledTransaction,
                               Source, SourceType, Transaction, TransferSuggestion,
                               TxChannel, TxStatus)
from app.services.projection_service import compute_projection, detect_low_balance, reconcile_scheduled


async def _setup(session):
    user = await get_single_user(session)
    bb = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal,
                bank_name="BB", balance=Decimal("300.00"),
                balance_date=datetime.now(timezone.utc), low_balance_threshold=Decimal("0"))
    inter = Source(user_id=user.id, type=SourceType.inter_pj, entity=Entity.empresa,
                   bank_name="Inter", balance=Decimal("5000.00"),
                   balance_date=datetime.now(timezone.utc))
    session.add_all([bb, inter]); await session.flush()
    session.add(ScheduledTransaction(user_id=user.id, source_id=bb.id,
                                     due_date=date.today() + timedelta(days=5),
                                     description="PAG BOLETO GRANDE", amount=Decimal("-500.00"),
                                     origin=ScheduledOrigin.ofx_futuro))
    await session.commit()
    return user, bb, inter


async def test_projecao_fica_negativa(session):
    user, bb, inter = await _setup(session)
    proj = await compute_projection(session, days=10)
    series = proj[str(bb.id)]
    assert any(p["saldo_projetado"] < 0 for p in series)


async def test_sugestao_criada_uma_vez(session):
    await _setup(session)
    s1 = await detect_low_balance(session)
    assert len(s1) == 1 and "PAG BOLETO GRANDE" in s1[0].reason
    s2 = await detect_low_balance(session)
    assert len(s2) == 0  # dedup da sugestão aberta


async def test_reconcile_marca_efetivado(session):
    user, bb, inter = await _setup(session)
    session.add(Transaction(user_id=user.id, source_id=bb.id, external_id="r-1",
                            amount=Decimal("-500.00"),
                            date=datetime.now(timezone.utc) + timedelta(days=5),
                            raw_description="PAG BOLETO GRANDE",
                            source_channel=TxChannel.ofx, entity=Entity.pessoal,
                            status=TxStatus.confirmada))
    await session.commit()
    await reconcile_scheduled(session)
    st = (await session.execute(select(ScheduledTransaction))).scalar_one()
    assert st.status == ScheduledStatus.efetivado
