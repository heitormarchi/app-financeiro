import io
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from pypdf import PdfReader


class PdfPasswordError(Exception):
    pass


def extract_pdf_text(content: bytes, password: str) -> str:
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted and not reader.decrypt(password):
        raise PdfPasswordError("senha incorreta")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


@dataclass
class FaturaEntry:
    date: date
    description: str
    city: str
    amount: Decimal
    direction: str  # 'D' | 'C'
    card_last4: str
    installment_no: int | None = None
    installment_total: int | None = None


@dataclass
class FaturaResult:
    entries: list[FaturaEntry] = field(default_factory=list)
    vencimento: date | None = None
    total: Decimal | None = None
    despesas_a_vencer: Decimal | None = None


VENC_RE = re.compile(r"VENCIMENTO\s*\n?\s*(\d{2})/(\d{2})/(\d{4})")
TOTAL_RE = re.compile(r"VALOR TOTAL DESTA FATURA\s*\n?\s*R\$\s*([\d.]+,\d{2})")
A_VENCER_RE = re.compile(r"DESPESAS A VENCER:\s*R\$\s*([\d.]+,\d{2})")
CARD_RE = re.compile(r"\(Cart\w*o\s+(\d{4})\)")
# "04/06RANCHO PARK SAMBAQUI IMBITUBA 247,31D" | "24/12GIASSI SUPER  06 DE 07 SAO JOSE 55,78D"
LINE_RE = re.compile(r"^(\d{2})/(\d{2})\s*(.+?)\s+([\d.]+,\d{2})([DC])\s*$")
PARC_RE = re.compile(r"^(.*?)\s+(\d{2}) DE (\d{2})\s+(.*)$")
SKIP_PATTERNS = ("TOTAL DA FATURA ANTERIOR", "OBRIGADO PELO PAGAMENTO", "TOTAL COMPRAS",
                 "TOTAL FINAL", "SALDO", "AJUSTE CRED")


def _brl(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def _infer_year(day: int, month: int, vencimento: date) -> date:
    # data da compra nunca é posterior ao vencimento; se ficaria, é do ano anterior
    candidate = date(vencimento.year, month, day)
    return candidate if candidate <= vencimento else date(vencimento.year - 1, month, day)


def parse_fatura_text(text: str) -> FaturaResult:
    result = FaturaResult()
    if m := VENC_RE.search(text):
        result.vencimento = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    if m := TOTAL_RE.search(text):
        result.total = _brl(m.group(1))
    if m := A_VENCER_RE.search(text):
        result.despesas_a_vencer = _brl(m.group(1))
    if result.vencimento is None:
        raise ValueError("vencimento não encontrado — layout mudou?")
    card = "0000"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if m := CARD_RE.search(line):
            card = m.group(1)
            continue
        m = LINE_RE.match(line)
        if not m:
            continue
        day, month, middle, value, direction = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4), m.group(5)
        upper = middle.upper()
        if any(p in upper for p in SKIP_PATTERNS):
            continue
        inst_no = inst_total = None
        if pm := PARC_RE.match(middle):
            middle = f"{pm.group(1)} {pm.group(4)}"
            inst_no, inst_total = int(pm.group(2)), int(pm.group(3))
        parts = middle.rsplit(" ", 1)
        desc, city = (parts[0], parts[1]) if len(parts) == 2 else (middle, "")
        result.entries.append(FaturaEntry(
            date=_infer_year(day, month, result.vencimento),
            description=desc.strip(), city=city.strip(), amount=_brl(value),
            direction=direction, card_last4=card,
            installment_no=inst_no, installment_total=inst_total))
    return result
