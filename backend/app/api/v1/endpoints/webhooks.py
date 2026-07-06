from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.services import whatsapp_service
from app.services.document_router import route_document

router = APIRouter(prefix="/webhooks")


@router.post("/whatsapp/{token}")
async def whatsapp_webhook(token: str, request: Request,
                           session: AsyncSession = Depends(get_session)):
    if not settings.evolution_webhook_token or token != settings.evolution_webhook_token:
        raise HTTPException(404)
    body = await request.json()
    data = body.get("data", {})
    jid = data.get("key", {}).get("remoteJid", "")
    if jid != settings.whatsapp_allowed_jid or data.get("key", {}).get("fromMe"):
        return {"ok": True}
    msg = data.get("message", {})
    doc = msg.get("documentMessage") or msg.get("imageMessage")
    if not doc:
        return {"ok": True}  # texto puro: ignorado no R1b
    content, mime = await whatsapp_service.get_media_bytes(data)
    filename = (msg.get("documentMessage") or {}).get("fileName", "imagem.jpg")
    reply = await route_document(session, filename, content, mime)
    if reply:
        await whatsapp_service.send_text(reply)
    return {"ok": True}
