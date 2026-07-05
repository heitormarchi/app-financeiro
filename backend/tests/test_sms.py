from decimal import Decimal
from pathlib import Path

from app.services.parsers.sms_parser import parse_caixa_sms

SMS_FIXTURES = [s.strip() for s in
                (Path(__file__).parent / "fixtures" / "sms_caixa_anon.txt").read_text(encoding="utf-8").split("\n\n")
                if s.strip()]
SMS_POSTO = SMS_FIXTURES[2]  # "... POSTO FL 53, R$ 150,00, 04/07 as 12:10. VISA final 3136 ..."
SMS_ASTERISCO = SMS_FIXTURES[0]  # merchant com "*" e "VISA VIRTUAL"


def test_parse_sms_valido():
    r = parse_caixa_sms(SMS_POSTO)
    assert r.amount == Decimal("150.00") and r.merchant == "POSTO FL 53" and r.card_last4 == "3136"


def test_parse_sms_merchant_com_asterisco_e_virtual():
    r = parse_caixa_sms(SMS_ASTERISCO)
    assert r.amount == Decimal("117.49") and r.merchant == "HOSTMF* FATURA 118136" and r.card_last4 == "6425"


def test_sms_ilegivel_retorna_none():
    assert parse_caixa_sms("CAIXA: informe de rendimentos disponivel") is None


async def test_endpoint_cria_provisoria(client, session):
    from sqlalchemy import select
    from app.core.auth import get_single_user
    from app.models.models import Entity, Source, SourceType, Transaction, TxStatus
    user = await get_single_user(session)
    session.add(Source(user_id=user.id, type=SourceType.caixa_cartao,
                       entity=Entity.pessoal, bank_name="Cartão Caixa"))
    await session.flush()
    r = await client.post("/api/v1/ingest/sms",
                          json={"text": SMS_POSTO, "received_at": "2026-07-04T12:10:00-03:00"})
    assert r.status_code == 200
    tx = (await session.execute(select(Transaction))).scalar_one()
    assert tx.status == TxStatus.provisoria and float(tx.amount) == -150.00


async def test_endpoint_sms_ilegivel_vira_pendencia(client, session):
    from sqlalchemy import select
    from app.models.models import Pendencia
    r = await client.post("/api/v1/ingest/sms",
                          json={"text": "CAIXA: promo imperdivel", "received_at": "2026-07-04T12:00:00-03:00"})
    assert r.status_code == 202
    assert (await session.execute(select(Pendencia))).scalar_one() is not None
