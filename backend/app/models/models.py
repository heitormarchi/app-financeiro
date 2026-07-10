import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from enum import Enum

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EnrichmentSource(str, Enum):
    dictionary = "dictionary"
    temporal = "temporal"
    collective = "collective"
    user = "user"
    llm = "llm"


class Entity(str, Enum):
    pessoal = "pessoal"
    empresa = "empresa"


class SourceType(str, Enum):
    bb_conta = "bb_conta"
    caixa_conta = "caixa_conta"
    caixa_cartao = "caixa_cartao"
    inter_pj = "inter_pj"


class TxChannel(str, Enum):
    ofx = "ofx"
    pdf = "pdf"
    sms = "sms"
    nfce = "nfce"
    inter = "inter"


class TxStatus(str, Enum):
    provisoria = "provisoria"
    confirmada = "confirmada"


class RawEventType(str, Enum):
    sms = "sms"
    nfce = "nfce"
    ofx = "ofx"
    pdf = "pdf"
    whatsapp_image = "whatsapp_image"


class Transport(str, Enum):
    upload = "upload"
    atalho = "atalho"
    whatsapp = "whatsapp"


class RawStatus(str, Enum):
    parsed = "parsed"
    failed = "failed"


class PendenciaType(str, Enum):
    parse_failed = "parse_failed"
    item_generico = "item_generico"
    sms_sem_fatura = "sms_sem_fatura"
    descrever_lancamento = "descrever_lancamento"


class ScheduledOrigin(str, Enum):
    ofx_futuro = "ofx_futuro"
    print_vision = "print_vision"
    inter_agendado = "inter_agendado"
    fatura_a_vencer = "fatura_a_vencer"
    manual = "manual"


class RecurrenceFrequency(str, Enum):
    mensal = "mensal"
    anual = "anual"


class ScheduledStatus(str, Enum):
    previsto = "previsto"
    efetivado = "efetivado"
    cancelado = "cancelado"


def _uuid_pk():
    return mapped_column(sa.Uuid, primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[SourceType] = mapped_column(String(30), nullable=False)
    entity: Mapped[Entity] = mapped_column(String(10), nullable=False, default=Entity.pessoal)
    bank_name: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_password_encrypted: Mapped[str | None] = mapped_column(Text)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    balance: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    balance_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    low_balance_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_description: Mapped[str] = mapped_column(Text, nullable=False)
    merchant: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))
    subcategory: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    enrichment_source: Mapped[EnrichmentSource | None] = mapped_column(String(50))
    source_channel: Mapped[TxChannel] = mapped_column(String(10), nullable=False)
    entity: Mapped[Entity] = mapped_column(String(10), nullable=False, default=Entity.pessoal)
    status: Mapped[TxStatus] = mapped_column(String(15), nullable=False, default=TxStatus.confirmada)
    is_invoice_payment: Mapped[bool] = mapped_column(default=False, nullable=False)
    installment_no: Mapped[int | None] = mapped_column()
    installment_total: Mapped[int | None] = mapped_column()
    original_purchase_date: Mapped[date_type | None] = mapped_column(sa.Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (sa.UniqueConstraint("source_id", "external_id", name="uq_tx_source_external"),)

    receipt_items: Mapped[list["ReceiptItem"]] = relationship(lazy="noload")


class RawEvent(Base):
    __tablename__ = "raw_events"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[RawEventType] = mapped_column(String(20), nullable=False)
    transport: Mapped[Transport] = mapped_column(String(10), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RawStatus] = mapped_column(String(10), nullable=False, default=RawStatus.parsed)
    error: Mapped[str | None] = mapped_column(Text)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReceiptItem(Base):
    __tablename__ = "receipt_items"
    id: Mapped[uuid.UUID] = _uuid_pk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transactions.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    product_code: Mapped[str | None] = mapped_column(String(60))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=1)
    unit: Mapped[str | None] = mapped_column(String(10))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))


class ItemCategoryRule(Base):
    __tablename__ = "item_category_rules"
    id: Mapped[uuid.UUID] = _uuid_pk()
    pattern: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100))


class Pendencia(Base):
    __tablename__ = "pendencias"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    type: Mapped[PendenciaType] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    keys: Mapped[dict] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ScheduledTransaction(Base):
    __tablename__ = "scheduled_transactions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    due_date: Mapped[date_type] = mapped_column(sa.Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    origin: Mapped[ScheduledOrigin] = mapped_column(String(20), nullable=False)
    status: Mapped[ScheduledStatus] = mapped_column(String(12), nullable=False, default=ScheduledStatus.previsto)
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transactions.id"))
    recurring_rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("recurring_rules.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    entity: Mapped[Entity] = mapped_column(String(10), nullable=False, default=Entity.pessoal)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"))
    frequency: Mapped[RecurrenceFrequency] = mapped_column(String(10), nullable=False)
    day: Mapped[int] = mapped_column(nullable=False)
    month: Mapped[int | None] = mapped_column()
    start_date: Mapped[date_type] = mapped_column(sa.Date, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TransferSuggestion(Base):
    __tablename__ = "transfer_suggestions"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    suggested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="sugerida")
    pix_id: Mapped[str | None] = mapped_column(String(100))


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"
    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date_type] = mapped_column(sa.Date, nullable=False)
    entity: Mapped[Entity] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CollectivePattern(Base):
    __tablename__ = "collective_patterns"
    id: Mapped[uuid.UUID] = _uuid_pk()
    raw_pattern: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    merchant: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(100))
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), default=0.5)
    sample_count: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
