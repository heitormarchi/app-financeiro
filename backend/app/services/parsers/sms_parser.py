import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")

SMS_RE = re.compile(
    r"Compra aprovada em\s+(?P<merchant>.+?),\s*R\$\s*(?P<valor>[\d.]+,\d{2}),\s*"
    r"(?P<dia>\d{2})/(?P<mes>\d{2})\s+as\s+(?P<hora>\d{2}):(?P<min>\d{2})\."
    r".*?final\s+(?P<card>\d{4})",
    re.I | re.S)


@dataclass
class SmsTx:
    amount: Decimal
    merchant: str
    when: datetime
    card_last4: str | None


def parse_caixa_sms(text: str, year: int | None = None) -> SmsTx | None:
    m = SMS_RE.search(text)
    if not m:
        return None
    now = datetime.now(TZ)
    year = year or now.year
    when = datetime(year, int(m.group("mes")), int(m.group("dia")),
                    int(m.group("hora")), int(m.group("min")), tzinfo=TZ)
    if when > now:  # SMS de dezembro processado em janeiro
        when = when.replace(year=year - 1)
    return SmsTx(amount=Decimal(m.group("valor").replace(".", "").replace(",", ".")),
                 merchant=m.group("merchant").strip(),
                 when=when, card_last4=m.group("card"))
