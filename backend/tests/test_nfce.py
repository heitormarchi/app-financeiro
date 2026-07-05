from decimal import Decimal
from pathlib import Path

from app.services.parsers.nfce_parser import parse_nfce_html

HTML = (Path(__file__).parent / "fixtures" / "nfce_sc_anon.html").read_text(encoding="utf-8")


def test_extrai_itens():
    r = parse_nfce_html(HTML)
    assert len(r.items) >= 1
    assert all(i.total_price > 0 for i in r.items)
    item = r.items[0]
    assert item.description == "TENIS ESPORTIVO MODELO X"
    assert item.product_code == "995626020344"
    assert item.quantity == Decimal("1")
    assert item.unit == "PR"
    assert item.unit_price == Decimal("499.99")
    assert item.total_price == Decimal("499.99")


def test_extrai_emitente_e_total():
    r = parse_nfce_html(HTML)
    assert r.emitente == "MERCADO EXEMPLO LTDA"
    assert r.cnpj == "12.345.678/0001-99"
    assert r.total == Decimal("499.99")
    assert r.when.strftime("%d/%m/%Y") == "26/05/2026"


async def test_scan_cria_ou_concilia(client, session, monkeypatch):
    from app.core.auth import get_single_user
    from app.models.models import Entity, Source, SourceType
    from app.services import nfce_service

    user = await get_single_user(session)
    session.add(Source(user_id=user.id, type=SourceType.caixa_cartao,
                       entity=Entity.pessoal, bank_name="Cartão Caixa"))
    await session.flush()

    async def fake_fetch(url):
        return HTML
    monkeypatch.setattr(nfce_service, "_fetch_html", fake_fetch)
    r = await client.post("/api/v1/nfce/scan",
                          json={"qr_url": "https://sat.sef.sc.gov.br/nfce/consulta?p=XXXX"})
    assert r.status_code == 200
    assert r.json()["itens"] >= 1


async def test_url_fora_da_sefaz_rejeitada(client):
    r = await client.post("/api/v1/nfce/scan", json={"qr_url": "https://malicioso.com/x"})
    assert r.status_code == 422
