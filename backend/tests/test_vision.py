from app.services.vision_service import parse_vision_json


def test_parse_json_valido():
    raw = '{"lancamentos": [{"due_date": "2026-07-10", "description": "PAG BOLETO MY DOGGIE", "amount": -690.00}]}'
    items = parse_vision_json(raw)
    assert len(items) == 1 and float(items[0].amount) == -690.00


def test_json_com_lixo_em_volta():
    raw = 'Aqui está:\n```json\n{"lancamentos": [{"due_date": "2026-07-15", "description": "CLARO", "amount": -81.90}]}\n```'
    assert len(parse_vision_json(raw)) == 1


def test_json_invalido_levanta():
    import pytest
    with pytest.raises(ValueError):
        parse_vision_json("não sei ler isso")
