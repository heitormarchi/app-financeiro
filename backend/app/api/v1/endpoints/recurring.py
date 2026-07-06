import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.core.database import get_session
from app.models.models import (Entity, RecurrenceFrequency, RecurringRule, ScheduledStatus,
                               ScheduledTransaction)
from app.services.recurring_service import materialize_recurring

router = APIRouter(prefix="/recurring")


class RecurringRuleBody(BaseModel):
    description: str
    amount: float
    entity: str = "pessoal"
    source_id: uuid.UUID | None = None
    frequency: str
    day: int = Field(ge=1, le=31)
    month: int | None = Field(default=None, ge=1, le=12)
    start_date: date | None = None


@router.get("")
async def list_recurring(session: AsyncSession = Depends(get_session)):
    rules = (await session.execute(select(RecurringRule).where(
        RecurringRule.active.is_(True)).order_by(RecurringRule.created_at.desc()))).scalars().all()
    return [
        {"id": str(r.id), "description": r.description, "amount": float(r.amount),
         "entity": r.entity, "source_id": str(r.source_id) if r.source_id else None,
         "frequency": r.frequency, "day": r.day, "month": r.month, "start_date": r.start_date}
        for r in rules
    ]


@router.post("")
async def create_recurring(body: RecurringRuleBody, session: AsyncSession = Depends(get_session)):
    try:
        freq = RecurrenceFrequency(body.frequency)
    except ValueError:
        raise HTTPException(422, "frequency deve ser 'mensal' ou 'anual'")
    if freq == RecurrenceFrequency.anual and body.month is None:
        raise HTTPException(422, "mês é obrigatório para recorrência anual")

    user = await get_single_user(session)
    rule = RecurringRule(
        user_id=user.id, description=body.description, amount=Decimal(str(body.amount)),
        entity=Entity(body.entity), source_id=body.source_id, frequency=freq,
        day=body.day, month=body.month, start_date=body.start_date or date.today(),
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    await materialize_recurring(session)
    return {"id": str(rule.id)}


@router.delete("/{rule_id}")
async def delete_recurring(rule_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    rule = await session.get(RecurringRule, rule_id)
    if rule is None:
        raise HTTPException(404)
    rule.active = False
    future = (await session.execute(select(ScheduledTransaction).where(
        ScheduledTransaction.recurring_rule_id == rule_id,
        ScheduledTransaction.status == ScheduledStatus.previsto,
        ScheduledTransaction.due_date >= date.today(),
    ))).scalars().all()
    for st in future:
        st.status = ScheduledStatus.cancelado
    await session.commit()
    return {"ok": True}
