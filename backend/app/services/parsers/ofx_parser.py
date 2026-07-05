import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

PSEUDO_NAMES = {"saldo anterior", "saldo do dia", "s a l d o"}
STMTTRN_RE = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S)
TAG_RE = re.compile(r"<(\w+)>([^<\r\n]*)")
ACCT_RE = re.compile(r"<ACCTID>([^<\r\n]*)")


@dataclass
class OfxTx:
    fitid: str | None
    date: datetime
    amount: Decimal
    name: str
    memo: str


@dataclass
class OfxResult:
    transactions: list[OfxTx] = field(default_factory=list)
    scheduled: list[OfxTx] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)
    account_id: str = ""


def _parse_date(raw: str) -> datetime:
    # "20260701000000[-3:BRT]" → aware datetime UTC-3 normalizado p/ UTC
    m = re.match(r"(\d{4})(\d{2})(\d{2})", raw)
    if not m:
        raise ValueError(raw)
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 1990:
        raise ValueError(raw)
    return datetime(y, mo, d, tzinfo=timezone.utc)


def parse_ofx(content: bytes) -> OfxResult:
    text = content.decode("utf-8", errors="replace")
    result = OfxResult()
    if m := ACCT_RE.search(text):
        result.account_id = m.group(1).strip()
    now = datetime.now(timezone.utc)
    for block in STMTTRN_RE.findall(text):
        tags = {k.upper(): v.strip() for k, v in TAG_RE.findall(block)}
        name = tags.get("NAME", "")
        try:
            amount = Decimal(tags.get("TRNAMT", "0"))
        except InvalidOperation:
            result.rejected.append(f"valor inválido: {tags.get('TRNAMT')}")
            continue
        try:
            date = _parse_date(tags.get("DTPOSTED", ""))
        except ValueError:
            result.rejected.append(f"data inválida: {tags.get('DTPOSTED', '?')} ({name})")
            continue
        if name.lower() in PSEUDO_NAMES or (amount == 0 and not tags.get("FITID")):
            continue
        tx = OfxTx(fitid=tags.get("FITID") or None, date=date, amount=amount,
                   name=name, memo=tags.get("MEMO", ""))
        (result.scheduled if date > now else result.transactions).append(tx)
    return result
