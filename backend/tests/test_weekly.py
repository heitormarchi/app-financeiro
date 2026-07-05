from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.core.auth import get_single_user
from app.models.models import Entity, Source, SourceType, Transaction, TxChannel, TxStatus
from app.services.weekly_service import compute_week_aggregates


async def test_agregados_da_semana(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB")
    session.add(src); await session.flush()
    session.add(Transaction(user_id=user.id, source_id=src.id, external_id="w1",
                            amount=Decimal("-200.00"),
                            date=datetime(2026, 6, 30, tzinfo=timezone.utc),
                            raw_description="MERCADO", category="Mercado",
                            source_channel=TxChannel.ofx, entity=Entity.pessoal,
                            status=TxStatus.confirmada))
    await session.commit()
    agg = await compute_week_aggregates(session, Entity.pessoal, week_start=date(2026, 6, 29))
    assert float(agg["total"]) == 200.00
    assert agg["por_categoria"]["Mercado"] == 200.00
