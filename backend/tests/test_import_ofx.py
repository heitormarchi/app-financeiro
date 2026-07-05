from pathlib import Path

from sqlalchemy import func, select

from app.core.auth import get_single_user
from app.models.models import Entity, ScheduledTransaction, Source, SourceType, Transaction

FIXTURE = (Path(__file__).parent / "fixtures" / "bb_extrato_anon.ofx").read_bytes()


async def _make_source(session):
    user = await get_single_user(session)
    src = Source(user_id=user.id, type=SourceType.bb_conta, entity=Entity.pessoal, bank_name="BB")
    session.add(src)
    await session.flush()
    return src


async def test_import_e_reimport_nao_duplica(client, session):
    src = await _make_source(session)
    files = {"file": ("extrato.ofx", FIXTURE, "application/octet-stream")}
    r1 = await client.post(f"/api/v1/imports/ofx?source_id={src.id}", files=files)
    assert r1.status_code == 200
    novas = r1.json()["novas"]
    assert novas > 0
    r2 = await client.post(f"/api/v1/imports/ofx?source_id={src.id}", files=files)
    assert r2.json()["novas"] == 0 and r2.json()["duplicadas"] == novas


async def test_futuros_viram_scheduled(client, session):
    src = await _make_source(session)
    files = {"file": ("extrato.ofx", FIXTURE, "application/octet-stream")}
    await client.post(f"/api/v1/imports/ofx?source_id={src.id}", files=files)
    n = (await session.execute(select(func.count(ScheduledTransaction.id)))).scalar()
    assert n >= 1


async def test_enriquecimento_aplicado(client, session):
    src = await _make_source(session)
    files = {"file": ("extrato.ofx", FIXTURE, "application/octet-stream")}
    await client.post(f"/api/v1/imports/ofx?source_id={src.id}", files=files)
    txs = (await session.execute(select(Transaction))).scalars().all()
    assert all(t.entity == Entity.pessoal for t in txs)
