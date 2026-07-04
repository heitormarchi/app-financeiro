from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.models import BankConnection, ConnectionStatus, Transaction, User, UserRoutine
from app.schemas.schemas import InsightOut, SyncOut, TransactionOut
from app.services.enrichment_service import enrich_transaction
from app.services.insight_service import generate_daily_insight
from app.services.pluggy_service import pluggy_service

router = APIRouter(prefix="/transactions", tags=["transactions"])

_INITIAL_HISTORY_DAYS = 90


@router.get("/", response_model=list[TransactionOut])
async def list_transactions(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user.id, Transaction.date >= since)
        .order_by(Transaction.date.desc())
    )
    return result.scalars().all()


@router.post("/sync", response_model=SyncOut)
async def sync_transactions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync transactions from Pluggy for all active bank connections of this user."""
    connections_result = await db.execute(
        select(BankConnection).where(
            BankConnection.user_id == user.id,
            BankConnection.status == ConnectionStatus.active,
        )
    )
    connections = list(connections_result.scalars().all())

    routine_result = await db.execute(select(UserRoutine).where(UserRoutine.user_id == user.id))
    routine = routine_result.scalar_one_or_none()

    total_new = 0
    errors: list[str] = []

    for connection in connections:
        if connection.last_synced_at:
            from_dt = connection.last_synced_at - timedelta(days=1)
        else:
            from_dt = datetime.now(timezone.utc) - timedelta(days=_INITIAL_HISTORY_DAYS)

        from_date = from_dt.strftime("%Y-%m-%d")
        to_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            accounts = await pluggy_service.get_accounts(connection.pluggy_item_id)
        except Exception as exc:
            connection.status = ConnectionStatus.error
            errors.append(f"connection {connection.id}: {exc}")
            continue

        for account in accounts:
            try:
                raw_txs = await pluggy_service.get_transactions(account["id"], from_date, to_date)
            except Exception as exc:
                errors.append(f"account {account['id']}: {exc}")
                continue

            for raw in raw_txs:
                pluggy_id = raw["id"]

                existing = await db.execute(
                    select(Transaction).where(Transaction.pluggy_transaction_id == pluggy_id)
                )
                if existing.scalar_one_or_none():
                    continue

                amount = float(raw["amount"])
                if raw.get("type") == "DEBIT":
                    amount = -abs(amount)

                raw_date = raw.get("date", "")
                tx_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

                tx = Transaction(
                    user_id=user.id,
                    connection_id=connection.id,
                    pluggy_transaction_id=pluggy_id,
                    amount=amount,
                    date=tx_date,
                    raw_description=raw.get("description") or raw.get("descriptionRaw", ""),
                )
                tx = await enrich_transaction(tx, routine, db)
                db.add(tx)
                total_new += 1

        connection.last_synced_at = datetime.now(timezone.utc)

    await db.commit()
    return SyncOut(new_transactions=total_new, connections_synced=len(connections), errors=errors)


@router.get("/insight", response_model=InsightOut)
async def get_insight(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a proactive AI insight for the user's recent transactions."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    transactions_result = await db.execute(
        select(Transaction)
        .where(Transaction.user_id == user.id, Transaction.date >= since)
        .order_by(Transaction.date.desc())
        .limit(50)
    )
    transactions = list(transactions_result.scalars().all())

    routine_result = await db.execute(select(UserRoutine).where(UserRoutine.user_id == user.id))
    routine = routine_result.scalar_one_or_none()

    enriched = []
    for tx in transactions:
        enriched.append(await enrich_transaction(tx, routine, db))

    message = await generate_daily_insight(enriched, period_days=days)
    return InsightOut(message=message, transactions_analyzed=len(enriched), period_days=days)
