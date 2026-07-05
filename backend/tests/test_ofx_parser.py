from datetime import datetime, timezone
from pathlib import Path

from app.services.parsers.ofx_parser import parse_ofx

FIXTURE = (Path(__file__).parent / "fixtures" / "bb_extrato_anon.ofx").read_bytes()


def test_filtra_pseudo_transacoes():
    r = parse_ofx(FIXTURE)
    names = [t.name for t in r.transactions]
    assert "Saldo Anterior" not in names and "Saldo do dia" not in names


def test_rejeita_data_invalida():
    r = parse_ofx(FIXTURE)
    assert any("00021130" in reason for reason in r.rejected)


def test_lancamento_futuro_vai_para_scheduled():
    r = parse_ofx(FIXTURE)
    assert len(r.scheduled) >= 1
    assert all(t.date > datetime.now(timezone.utc) for t in r.scheduled)


def test_transacao_normal():
    r = parse_ofx(FIXTURE)
    tx = next(t for t in r.transactions if t.fitid == "70.101")
    assert float(tx.amount) == -1641.39 and tx.name == "Pagamento de Boleto"
