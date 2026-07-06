from decimal import Decimal
from unittest.mock import AsyncMock, patch

from app.core.auth import get_single_user
from app.models.models import TransferSuggestion


async def _sugestao(session):
    user = await get_single_user(session)
    s = TransferSuggestion(user_id=user.id, amount=Decimal("500.00"),
                           reason="Saldo BB ficará -R$ 200 em 16/07")
    session.add(s); await session.commit()
    return s


async def test_confirmar_executa_pix(client, session):
    s = await _sugestao(session)
    with patch("app.api.v1.endpoints.transfers.InterClient") as MC:
        MC.return_value.send_pix = AsyncMock(return_value="E2E123")
        r = await client.post(f"/api/v1/transfers/{s.id}/confirm", json={"amount": "450.00"})
    assert r.status_code == 200
    await session.refresh(s)
    assert s.status == "executada" and s.pix_id == "E2E123"


async def test_falha_da_api_mantem_sugerida(client, session):
    s = await _sugestao(session)
    with patch("app.api.v1.endpoints.transfers.InterClient") as MC:
        MC.return_value.send_pix = AsyncMock(side_effect=RuntimeError("api fora"))
        r = await client.post(f"/api/v1/transfers/{s.id}/confirm", json={"amount": "450.00"})
    assert r.status_code == 502
    await session.refresh(s)
    assert s.status == "sugerida"


async def test_dismiss(client, session):
    s = await _sugestao(session)
    r = await client.post(f"/api/v1/transfers/{s.id}/dismiss")
    assert r.status_code == 200
    await session.refresh(s)
    assert s.status == "recusada"
