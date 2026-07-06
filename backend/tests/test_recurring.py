import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.core.auth import get_single_user
from app.models.models import RecurrenceFrequency, RecurringRule, ScheduledStatus, ScheduledTransaction
from app.services.date_utils import add_months
from app.services.recurring_service import materialize_recurring


async def test_regra_mensal_materializa_proximas_ocorrencias(session):
    user = await get_single_user(session)
    session.add(RecurringRule(user_id=user.id, description="Aluguel", amount=-1900,
                              frequency=RecurrenceFrequency.mensal, day=5,
                              start_date=date.today()))
    await session.commit()

    created = await materialize_recurring(session, months_horizon=12)
    assert len(created) >= 11  # ~12 meses, menos possivelmente o dia 5 já ter passado
    assert all(s.description == "Aluguel" for s in created)
    assert all(s.due_date.day == 5 for s in created)


async def test_regra_anual_materializa_uma_ocorrencia(session):
    user = await get_single_user(session)
    daqui_a_2_meses = add_months(date.today(), 2)
    session.add(RecurringRule(user_id=user.id, description="IPVA", amount=-850,
                              frequency=RecurrenceFrequency.anual,
                              day=daqui_a_2_meses.day, month=daqui_a_2_meses.month,
                              start_date=date.today()))
    await session.commit()

    created = await materialize_recurring(session, months_horizon=12)
    assert len(created) == 1
    assert created[0].description == "IPVA"
    assert created[0].due_date.month == daqui_a_2_meses.month


async def test_materialize_nao_duplica(session):
    user = await get_single_user(session)
    session.add(RecurringRule(user_id=user.id, description="Aluguel", amount=-1900,
                              frequency=RecurrenceFrequency.mensal, day=5,
                              start_date=date.today()))
    await session.commit()
    primeira = await materialize_recurring(session, months_horizon=6)
    segunda = await materialize_recurring(session, months_horizon=6)
    assert len(segunda) == 0
    total = (await session.execute(select(ScheduledTransaction))).scalars().all()
    assert len(total) == len(primeira)


async def test_criar_e_listar_via_api(client):
    r = await client.post("/api/v1/recurring", json={
        "description": "Aluguel", "amount": -1900, "frequency": "mensal", "day": 5,
    })
    assert r.status_code == 200
    r2 = await client.get("/api/v1/recurring")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["description"] == "Aluguel"

    r3 = await client.get("/api/v1/scheduled?status=previsto")
    assert len(r3.json()) >= 1
    assert any(i["origin"] == "manual" for i in r3.json())


async def test_anual_sem_mes_retorna_erro(client):
    r = await client.post("/api/v1/recurring", json={
        "description": "IPVA", "amount": -850, "frequency": "anual", "day": 15,
    })
    assert r.status_code == 422


async def test_excluir_cancela_futuros(client, session):
    r = await client.post("/api/v1/recurring", json={
        "description": "Aluguel", "amount": -1900, "frequency": "mensal", "day": 5,
    })
    rule_id = r.json()["id"]
    r2 = await client.delete(f"/api/v1/recurring/{rule_id}")
    assert r2.status_code == 200

    rule = await session.get(RecurringRule, uuid.UUID(rule_id))
    assert rule.active is False
    futuros = (await session.execute(select(ScheduledTransaction).where(
        ScheduledTransaction.recurring_rule_id == uuid.UUID(rule_id)))).scalars().all()
    assert all(s.status == ScheduledStatus.cancelado for s in futuros)
