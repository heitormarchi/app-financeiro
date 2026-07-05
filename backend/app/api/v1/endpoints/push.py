from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.core.config import settings
from app.core.database import get_session
from app.models.models import PushSubscription
from app.services.weekly_service import run_weekly_job

router = APIRouter(prefix="/push")


class SubscriptionBody(BaseModel):
    endpoint: str
    keys: dict


@router.get("/vapid-public-key")
async def vapid_public_key():
    return {"key": settings.vapid_public_key}


@router.post("/subscriptions")
async def create_subscription(body: SubscriptionBody, session: AsyncSession = Depends(get_session)):
    user = await get_single_user(session)
    existing = (await session.execute(select(PushSubscription).where(
        PushSubscription.endpoint == body.endpoint))).scalar_one_or_none()
    if existing is None:
        session.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, keys=body.keys))
        await session.commit()
    return {"ok": True}


@router.post("/test-weekly")
async def test_weekly(session: AsyncSession = Depends(get_session)):
    await run_weekly_job(session)
    return {"ok": True}
