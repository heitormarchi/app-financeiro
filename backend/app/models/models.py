import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EnrichmentSource(str, Enum):
    dictionary = "dictionary"
    temporal = "temporal"
    collective = "collective"
    user = "user"
    llm = "llm"


class ConnectionStatus(str, Enum):
    active = "active"
    error = "error"
    revoked = "revoked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    bank_connections: Mapped[list["BankConnection"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    routine: Mapped["UserRoutine"] = relationship(back_populates="user", uselist=False)


class BankConnection(Base):
    __tablename__ = "bank_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    pluggy_item_id: Mapped[str] = mapped_column(String(255), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConnectionStatus] = mapped_column(String(50), default=ConnectionStatus.active)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="bank_connections")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="connection")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bank_connections.id"), nullable=False)

    # Raw data from Pluggy
    pluggy_transaction_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Enriched data
    merchant: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    subcategory: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    enrichment_source: Mapped[EnrichmentSource | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="transactions")
    connection: Mapped["BankConnection"] = relationship(back_populates="transactions")


class UserRoutine(Base):
    __tablename__ = "user_routines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    work_start: Mapped[str | None] = mapped_column(String(5))   # "HH:MM"
    work_end: Mapped[str | None] = mapped_column(String(5))     # "HH:MM"
    work_days: Mapped[list | None] = mapped_column(JSONB)       # [0,1,2,3,4] = seg-sex
    patterns: Mapped[dict | None] = mapped_column(JSONB)        # padrões aprendidos
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="routine")


class CollectivePattern(Base):
    __tablename__ = "collective_patterns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_pattern: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0.5)
    sample_count: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
