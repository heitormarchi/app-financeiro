import hmac

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import User

SINGLE_USER_EMAIL = "heitormarchicursos@gmail.com"


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not hmac.compare_digest(x_api_key, settings.app_api_key):
        raise HTTPException(status_code=401, detail="API key inválida")


async def get_single_user(session: AsyncSession) -> User:
    user = (await session.execute(select(User).limit(1))).scalar_one_or_none()
    if user is None:
        user = User(email=SINGLE_USER_EMAIL)
        session.add(user)
        await session.flush()
    return user
