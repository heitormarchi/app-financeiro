import base64

import httpx

from app.core.config import settings


async def send_text(text: str) -> None:
    async with httpx.AsyncClient(timeout=30) as c:
        await c.post(
            f"{settings.evolution_base_url}/message/sendText/{settings.evolution_instance}",
            headers={"apikey": settings.evolution_api_key},
            json={"number": settings.whatsapp_allowed_jid.split("@")[0], "text": text})


async def get_media_bytes(message_data: dict) -> tuple[bytes, str]:
    msg = message_data.get("message", {})
    mime = (msg.get("documentMessage") or msg.get("imageMessage") or {}).get("mimetype", "")
    async with httpx.AsyncClient(timeout=60) as c:
        resp = await c.post(
            f"{settings.evolution_base_url}/chat/getBase64FromMediaMessage/{settings.evolution_instance}",
            headers={"apikey": settings.evolution_api_key},
            json={"message": message_data})
        resp.raise_for_status()
        return base64.b64decode(resp.json()["base64"]), mime
