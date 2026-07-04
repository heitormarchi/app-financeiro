from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import BankConnection, User
from app.schemas.schemas import BankConnectionCreate, BankConnectionOut
from app.services.pluggy_service import pluggy_service

router = APIRouter(prefix="/connections", tags=["connections"])


@router.post("/connect-token")
async def get_connect_token(user: User = Depends(get_current_user)):
    """Returns a Pluggy Connect Token for the frontend Widget."""
    token = await pluggy_service.create_connect_token(str(user.id))
    return {"connect_token": token}


@router.post("/", response_model=BankConnectionOut)
async def create_connection(
    payload: BankConnectionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a bank connection after the user completes the Pluggy Widget flow."""
    connection = BankConnection(
        user_id=user.id,
        pluggy_item_id=payload.pluggy_item_id,
        bank_name=payload.bank_name,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get("/", response_model=list[BankConnectionOut])
async def list_connections(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(BankConnection).where(BankConnection.user_id == user.id)
    )
    return result.scalars().all()
