import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


# --- User ---

class UserCreate(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Bank Connection ---

class BankConnectionCreate(BaseModel):
    pluggy_item_id: str
    bank_name: str


class BankConnectionOut(BaseModel):
    id: uuid.UUID
    pluggy_item_id: str
    bank_name: str
    status: str
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Transaction ---

class TransactionOut(BaseModel):
    id: uuid.UUID
    amount: float
    date: datetime
    raw_description: str
    merchant: str | None
    category: str | None
    subcategory: str | None
    confidence: float | None
    enrichment_source: str | None

    model_config = {"from_attributes": True}


# --- Insight ---

class InsightOut(BaseModel):
    message: str
    transactions_analyzed: int
    period_days: int


# --- Sync ---

class SyncOut(BaseModel):
    new_transactions: int
    connections_synced: int
    errors: list[str]
