"""
5-layer transaction enrichment pipeline.

Layer 1: Regex dictionary          → ~60% coverage
Layer 2: Temporal/routine inference → +15%
Layer 3: Collective intelligence    → +10%
Layer 4: LLM (Claude)               → remaining + insight generation

Phase B/C: implement each layer.
"""
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import CollectivePattern, EnrichmentSource, Transaction, UserRoutine

# --- Layer 1: Regex dictionary ---

MERCHANT_PATTERNS: list[tuple[re.Pattern, str, str, str]] = [
    # (pattern, merchant, category, subcategory)
    (re.compile(r"IFOOD|IFOOD", re.I), "iFood", "Alimentação", "Delivery"),
    (re.compile(r"RAPPI", re.I), "Rappi", "Alimentação", "Delivery"),
    (re.compile(r"UBER\s*EATS", re.I), "Uber Eats", "Alimentação", "Delivery"),
    (re.compile(r"UBER(?!\s*EATS)", re.I), "Uber", "Transporte", "Aplicativo"),
    (re.compile(r"99\s*APP|99POP", re.I), "99", "Transporte", "Aplicativo"),
    (re.compile(r"NETFLIX", re.I), "Netflix", "Entretenimento", "Streaming"),
    (re.compile(r"SPOTIFY", re.I), "Spotify", "Entretenimento", "Streaming"),
    (re.compile(r"AMAZON\s*PRIME|PRIME\s*VIDEO", re.I), "Amazon Prime", "Entretenimento", "Streaming"),
    (re.compile(r"MERCADO\s*LIVRE|MERCADOLIVRE|MERCPAGO", re.I), "Mercado Livre", "Compras", "E-commerce"),
    (re.compile(r"AMAZON", re.I), "Amazon", "Compras", "E-commerce"),
    (re.compile(r"SHOPEE", re.I), "Shopee", "Compras", "E-commerce"),
    (re.compile(r"FARMAC|DROGASIL|DROGA\s*RAIA|PACHECO|ULTRAFARMA", re.I), "Farmácia", "Saúde", "Farmácia"),
    (re.compile(r"EXTRA|CARREFOUR|P\s*?O\s*?N\s*?T\s*?O\s*?FRIO|WALMART|ATACADAO|ASSAI", re.I), "Supermercado", "Mercado", "Supermercado"),
]


def match_dictionary(raw_description: str) -> tuple[str, str, str, float] | None:
    """Returns (merchant, category, subcategory, confidence) or None."""
    for pattern, merchant, category, subcategory in MERCHANT_PATTERNS:
        if pattern.search(raw_description):
            return merchant, category, subcategory, 0.85
    return None


# --- Layer 2: Temporal inference ---

def infer_from_routine(
    raw_description: str,
    transaction_hour: int,
    routine: UserRoutine | None,
) -> dict | None:
    """
    Resolves ambiguities (e.g. Uber work vs leisure) using the user's routine.
    Returns enrichment override dict or None.
    """
    if routine is None:
        return None

    is_uber = bool(re.search(r"UBER(?!\s*EATS)", raw_description, re.I))
    if not is_uber:
        return None

    work_days: list = routine.work_days or [0, 1, 2, 3, 4]
    work_start_h = int((routine.work_start or "08:00").split(":")[0])
    work_end_h = int((routine.work_end or "18:00").split(":")[0])

    commute_window = 2  # hours around work start/end
    is_commute = (
        abs(transaction_hour - work_start_h) <= commute_window
        or abs(transaction_hour - work_end_h) <= commute_window
    )

    if is_commute:
        return {"subcategory": "Trabalho", "confidence": 0.75, "enrichment_source": EnrichmentSource.temporal}
    return {"subcategory": "Lazer", "confidence": 0.70, "enrichment_source": EnrichmentSource.temporal}


# --- Layer 3: Collective intelligence ---

async def match_collective(raw_description: str, db: AsyncSession) -> tuple[str, str, str, float] | None:
    """Look up aggregated patterns from other users."""
    from sqlalchemy import select

    # Normalize: uppercase, strip digits and special chars for matching
    normalized = re.sub(r"[\d*#]", "", raw_description).strip().upper()

    result = await db.execute(
        select(CollectivePattern)
        .where(CollectivePattern.raw_pattern == normalized)
        .where(CollectivePattern.confidence >= 0.6)
    )
    pattern = result.scalar_one_or_none()
    if pattern:
        return pattern.merchant, pattern.category, pattern.subcategory or "", pattern.confidence
    return None


# --- Main enrichment orchestrator ---

async def enrich_transaction(transaction: Transaction, routine: UserRoutine | None, db: AsyncSession) -> Transaction:
    """Run the 4-layer pipeline (LLM is called separately during insight generation)."""

    # Layer 1
    result = match_dictionary(transaction.raw_description)
    if result:
        merchant, category, subcategory, confidence = result
        transaction.merchant = merchant
        transaction.category = category
        transaction.subcategory = subcategory
        transaction.confidence = confidence
        transaction.enrichment_source = EnrichmentSource.dictionary

    # Layer 2: try to refine subcategory using routine
    if transaction.merchant == "Uber" and routine:
        override = infer_from_routine(
            transaction.raw_description,
            transaction.date.hour,
            routine,
        )
        if override:
            transaction.subcategory = override.get("subcategory", transaction.subcategory)
            transaction.confidence = override.get("confidence", transaction.confidence)
            transaction.enrichment_source = override.get("enrichment_source", transaction.enrichment_source)

    # Layer 3: collective patterns (only if still unenriched)
    if not transaction.merchant:
        collective = await match_collective(transaction.raw_description, db)
        if collective:
            merchant, category, subcategory, confidence = collective
            transaction.merchant = merchant
            transaction.category = category
            transaction.subcategory = subcategory
            transaction.confidence = confidence
            transaction.enrichment_source = EnrichmentSource.collective

    return transaction
