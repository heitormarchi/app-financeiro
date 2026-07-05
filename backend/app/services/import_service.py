import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.models.models import (EnrichmentSource, RawEvent, RawEventType,
                               ScheduledOrigin, ScheduledTransaction, Source,
                               Transaction, Transport, TxChannel, TxStatus)
from app.services.enrichment_service import match_dictionary
from app.services.parsers.ofx_parser import parse_ofx


@dataclass
class ImportReport:
    novas: int = 0
    duplicadas: int = 0
    rejeitadas: int = 0
    futuros: int = 0


def make_external_id(*parts: str) -> str:
    return hashlib.sha256("|".join(p.strip().lower() for p in parts).encode()).hexdigest()[:32]


async def enrich_and_fill(tx: Transaction) -> None:
    if match := match_dictionary(tx.raw_description):
        tx.merchant, tx.category, tx.subcategory, tx.confidence = match
        tx.enrichment_source = EnrichmentSource.dictionary


async def _existing_ids(session: AsyncSession, source_id) -> set[str]:
    rows = await session.execute(select(Transaction.external_id).where(Transaction.source_id == source_id))
    return {r[0] for r in rows}


INVOICE_PAYMENT_PATTERNS = ("PAG FATURA", "PAGTO FATURA", "PAGAMENTO FATURA", "PGTO CARTAO CRED")


def _is_invoice_payment(name: str, memo: str, source: Source) -> bool:
    text = f"{name} {memo}".upper()
    return any(p in text for p in INVOICE_PAYMENT_PATTERNS)


async def import_ofx(session: AsyncSession, source: Source, content: bytes,
                     transport: Transport) -> ImportReport:
    user = await get_single_user(session)
    session.add(RawEvent(user_id=user.id, type=RawEventType.ofx, transport=transport,
                         payload=content.decode("utf-8", errors="replace")))
    parsed = parse_ofx(content)
    report = ImportReport(rejeitadas=len(parsed.rejected))
    existing = await _existing_ids(session, source.id)
    for t in parsed.transactions:
        ext = t.fitid or make_external_id(t.date.isoformat(), str(t.amount), t.name, t.memo)
        if ext in existing:
            report.duplicadas += 1
            continue
        tx = Transaction(user_id=user.id, source_id=source.id, external_id=ext,
                         amount=t.amount, date=t.date,
                         raw_description=f"{t.name} {t.memo}".strip(),
                         source_channel=TxChannel.ofx, entity=source.entity,
                         status=TxStatus.confirmada,
                         is_invoice_payment=_is_invoice_payment(t.name, t.memo, source))
        await enrich_and_fill(tx)
        session.add(tx)
        existing.add(ext)
        report.novas += 1
    for t in parsed.scheduled:
        dup = await session.execute(select(ScheduledTransaction).where(
            ScheduledTransaction.due_date == t.date.date(),
            ScheduledTransaction.amount == t.amount,
            ScheduledTransaction.description == f"{t.name} {t.memo}".strip()))
        if dup.scalar_one_or_none():
            continue
        session.add(ScheduledTransaction(user_id=user.id, source_id=source.id,
                                         due_date=t.date.date(), amount=t.amount,
                                         description=f"{t.name} {t.memo}".strip(),
                                         origin=ScheduledOrigin.ofx_futuro))
        report.futuros += 1
    await session.commit()
    return report
