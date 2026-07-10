"""Regex dictionary enrichment — matches raw transaction descriptions to merchant/category."""
import re

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
