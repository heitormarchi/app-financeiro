from datetime import date
from pathlib import Path

from app.services.parsers.fatura_parser import parse_fatura_text

TEXT = (Path(__file__).parent / "fixtures" / "fatura_texto_anon.txt").read_text(encoding="utf-8")


def test_metadados():
    r = parse_fatura_text(TEXT)
    assert r.vencimento == date(2026, 6, 21)
    assert r.despesas_a_vencer is not None


def test_compras_por_cartao():
    r = parse_fatura_text(TEXT)
    assert {e.card_last4 for e in r.entries} == {"3136", "6425"}


def test_parcelada():
    r = parse_fatura_text(TEXT)
    p = next(e for e in r.entries if e.installment_no is not None)
    assert 1 <= p.installment_no <= p.installment_total


def test_filtra_informativas_e_pagamento():
    r = parse_fatura_text(TEXT)
    descrs = " ".join(e.description for e in r.entries).upper()
    assert "TOTAL DA FATURA ANTERIOR" not in descrs
    assert "OBRIGADO PELO PAGAMENTO" not in descrs


def test_ano_inferido_de_vencimento():
    r = parse_fatura_text(TEXT)
    dez = next(e for e in r.entries if e.date.month == 12)
    assert dez.date.year == 2025
