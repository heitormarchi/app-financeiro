import json
from pathlib import Path

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "evolution_document.json").read_text(encoding="utf-8"))


async def test_token_errado_404(client):
    r = await client.post("/api/v1/webhooks/whatsapp/token-errado", json=FIXTURE)
    assert r.status_code == 404


async def test_jid_nao_autorizado_ignorado(client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "evolution_webhook_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_allowed_jid", "5548999990000@s.whatsapp.net")
    payload = json.loads(json.dumps(FIXTURE))
    payload["data"]["key"]["remoteJid"] = "5511888887777@s.whatsapp.net"
    r = await client.post("/api/v1/webhooks/whatsapp/tok", json=payload)
    assert r.status_code == 200 and r.json() == {"ok": True}  # silencioso


async def test_documento_ofx_roteado(client, session, monkeypatch):
    from app.core.config import settings
    from app.services import whatsapp_service
    monkeypatch.setattr(settings, "evolution_webhook_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_allowed_jid", FIXTURE["data"]["key"]["remoteJid"])
    ofx = (Path(__file__).parent / "fixtures" / "bb_extrato_anon.ofx").read_bytes()

    async def fake_media(data):
        return ofx, "application/octet-stream"
    sent: list[str] = []

    async def fake_send(text):
        sent.append(text)
    monkeypatch.setattr(whatsapp_service, "get_media_bytes", fake_media)
    monkeypatch.setattr(whatsapp_service, "send_text", fake_send)
    # seed da fonte BB
    from app.core.auth import get_single_user
    from app.models.models import Entity, Source, SourceType
    user = await get_single_user(session)
    session.add(Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB"))
    await session.commit()
    r = await client.post("/api/v1/webhooks/whatsapp/tok", json=FIXTURE)
    assert r.status_code == 200
    assert sent and "novas" in sent[0]
