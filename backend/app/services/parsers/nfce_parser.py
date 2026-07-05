import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup


@dataclass
class NfceItem:
    description: str
    product_code: str | None
    quantity: Decimal
    unit: str | None
    unit_price: Decimal | None
    total_price: Decimal


@dataclass
class NfceResult:
    emitente: str = ""
    cnpj: str = ""
    when: datetime | None = None
    total: Decimal = Decimal("0")
    items: list[NfceItem] = field(default_factory=list)


def _num(s: str) -> Decimal:
    return Decimal(re.sub(r"[^\d,]", "", s).replace(",", "."))


def parse_nfce_html(html: str) -> NfceResult:
    soup = BeautifulSoup(html, "lxml")
    r = NfceResult()
    if el := soup.select_one(".txtTopo"):
        r.emitente = el.get_text(strip=True)
    if m := re.search(r"CNPJ:?\s*([\d./-]{14,18})", soup.get_text()):
        r.cnpj = m.group(1)
    if m := re.search(r"Emiss[ãa]o:?\s*(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2}:\d{2})?", soup.get_text()):
        d = datetime.strptime(m.group(1), "%d/%m/%Y")
        r.when = d.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))
    if el := soup.select_one(".totalNumb.txtMax"):
        r.total = _num(el.get_text())
    for row in soup.select("#tabResult tr"):
        tit = row.select_one(".txtTit")
        val = row.select_one(".valor")
        if not tit or not val:
            continue
        qtd = row.select_one(".Rqtd")
        un = row.select_one(".RUN")
        vu = row.select_one(".RvlUnit")
        cod = row.select_one(".RCod")
        r.items.append(NfceItem(
            description=tit.get_text(strip=True),
            product_code=re.sub(r"\D", "", cod.get_text()) if cod else None,
            quantity=_num(qtd.get_text().split(":")[-1]) if qtd else Decimal("1"),
            unit=un.get_text(strip=True).split(":")[-1].strip() if un else None,
            unit_price=_num(vu.get_text().split(":")[-1]) if vu else None,
            total_price=_num(val.get_text())))
    if not r.items:
        raise ValueError("nenhum item encontrado — layout da SEFAZ mudou?")
    return r
