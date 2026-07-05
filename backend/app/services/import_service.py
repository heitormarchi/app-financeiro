import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as tz
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_single_user
from app.models.models import (EnrichmentSource, Pendencia, PendenciaType,
                               RawEvent, RawEventType, ScheduledOrigin,
                               ScheduledTransaction, Source, Transaction,
                               Transport, TxChannel, TxStatus)
from app.services.enrichment_service import match_dictionary
from app.services.parsers.fatura_parser import (FaturaEntry, PdfPasswordError,
                                                extract_pdf_text, parse_fatura_text)
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


async def import_fatura(session: AsyncSession, source: Source, content, transport: Transport,
                        pre_extracted: bool = False) -> ImportReport:
    user = await get_single_user(session)
    if pre_extracted:
        text = content
    else:
        if not source.pdf_password_encrypted:
            raise PdfPasswordError("senha do PDF não configurada para esta fonte")
        from app.core.crypto import decrypt_str
        text = extract_pdf_text(content, decrypt_str(source.pdf_password_encrypted))
    session.add(RawEvent(user_id=user.id, type=RawEventType.pdf, transport=transport, payload=text))
    parsed = parse_fatura_text(text)
    report = ImportReport()
    existing = await _existing_ids(session, source.id)
    for e in parsed.entries:
        if e.direction == "C":
            continue  # créditos/ajustes não são gasto
        ext = make_external_id(e.card_last4, e.date.isoformat(), e.description,
                               str(e.amount), str(e.installment_no or 0))
        if ext in existing:
            report.duplicadas += 1
            continue
        matched = await _match_provisoria(session, source, e)
        if matched is not None:
            matched.status = TxStatus.confirmada
            matched.external_id = ext
            existing.add(ext)
            report.duplicadas += 1
            continue
        tx = Transaction(user_id=user.id, source_id=source.id, external_id=ext,
                         amount=-e.amount, date=datetime(e.date.year, e.date.month, e.date.day, tzinfo=tz.utc),
                         raw_description=f"{e.description} {e.city}".strip(),
                         source_channel=TxChannel.pdf, entity=source.entity,
                         status=TxStatus.confirmada,
                         installment_no=e.installment_no, installment_total=e.installment_total,
                         original_purchase_date=e.date if e.installment_no else None)
        await enrich_and_fill(tx)
        session.add(tx)
        existing.add(ext)
        report.novas += 1
    if parsed.despesas_a_vencer and parsed.vencimento:
        session.add(ScheduledTransaction(user_id=user.id, source_id=source.id,
                                         due_date=parsed.vencimento,
                                         description="Fatura Cartão Caixa (despesas a vencer)",
                                         amount=-parsed.despesas_a_vencer,
                                         origin=ScheduledOrigin.fatura_a_vencer))
        report.futuros += 1
    await _flag_sms_sem_fatura(session, source, parsed)
    await session.commit()
    return report


async def _match_provisoria(session: AsyncSession, source: Source, e: FaturaEntry) -> Transaction | None:
    center = datetime(e.date.year, e.date.month, e.date.day, tzinfo=tz.utc)
    rows = (await session.execute(select(Transaction).where(
        Transaction.source_id == source.id,
        Transaction.status == TxStatus.provisoria,
        Transaction.amount == -e.amount,
        Transaction.date >= center - timedelta(days=1),
        Transaction.date <= center + timedelta(days=1)))).scalars().all()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    return max(rows, key=lambda t: SequenceMatcher(
        None, t.raw_description.upper(), e.description.upper()).ratio())


async def _flag_sms_sem_fatura(session: AsyncSession, source: Source, parsed) -> None:
    # provisórias anteriores ao período coberto e não conciliadas viram pendência
    user = await get_single_user(session)
    cutoff = min((e.date for e in parsed.entries), default=None)
    if cutoff is None:
        return
    stale = (await session.execute(select(Transaction).where(
        Transaction.source_id == source.id,
        Transaction.status == TxStatus.provisoria,
        Transaction.date < datetime(cutoff.year, cutoff.month, cutoff.day, tzinfo=tz.utc)))).scalars().all()
    for t in stale:
        session.add(Pendencia(user_id=user.id, type=PendenciaType.sms_sem_fatura,
                              payload={"transaction_id": str(t.id), "descricao": t.raw_description,
                                       "valor": str(t.amount)}))
