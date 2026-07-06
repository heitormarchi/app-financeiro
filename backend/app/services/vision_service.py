import base64
import json
import re
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ValidationError
from sqlalchemy import select

from app.core.auth import get_single_user
from app.core.config import settings
from app.models.models import (RawEvent, RawEventType, RawStatus, ScheduledOrigin,
                               ScheduledTransaction, Transport)
from app.services.insight_service import client  # AsyncOpenAI já configurado p/ OpenRouter

VISION_PROMPT = """Você lê um print de tela de app bancário brasileiro com lançamentos futuros/agendados.
Extraia TODOS os lançamentos em JSON: {"lancamentos": [{"due_date": "YYYY-MM-DD", "description": "...", "amount": -123.45}]}
Regras: amount negativo para débitos; ignore totais e propaganda; se o ano não aparecer, use o ano do contexto do mês mostrado. Responda SÓ o JSON."""


class VisionScheduled(BaseModel):
    due_date: date
    description: str
    amount: Decimal


def parse_vision_json(raw: str) -> list[VisionScheduled]:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    try:
        data = json.loads(m.group(0))
        return [VisionScheduled(**item) for item in data.get("lancamentos", [])]
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"JSON inválido da visão: {e}")


async def extract_scheduled_from_image(session, image: bytes) -> int:
    user = await get_single_user(session)
    b64 = base64.b64encode(image).decode()
    resp = await client.chat.completions.create(
        model=settings.openrouter_vision_model, max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": VISION_PROMPT},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}])
    raw_text = resp.choices[0].message.content
    event = RawEvent(user_id=user.id, type=RawEventType.whatsapp_image,
                     transport=Transport.whatsapp, payload=raw_text)
    session.add(event)
    try:
        items = parse_vision_json(raw_text)
    except ValueError as e:
        event.status = RawStatus.failed
        event.error = str(e)
        await session.commit()
        raise
    created = 0
    for it in items:
        dup = (await session.execute(select(ScheduledTransaction).where(
            ScheduledTransaction.due_date == it.due_date,
            ScheduledTransaction.amount == it.amount,
            ScheduledTransaction.description == it.description))).scalar_one_or_none()
        if dup:
            continue
        session.add(ScheduledTransaction(user_id=user.id, due_date=it.due_date,
                                         description=it.description, amount=it.amount,
                                         origin=ScheduledOrigin.print_vision))
        created += 1
    await session.commit()
    return created
