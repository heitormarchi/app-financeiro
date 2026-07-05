async def test_listar_e_resolver(client, session):
    from sqlalchemy import select
    from app.core.auth import get_single_user
    from app.models.models import Pendencia, PendenciaType
    user = await get_single_user(session)
    p = Pendencia(user_id=user.id, type=PendenciaType.descrever_lancamento,
                  payload={"transaction_id": None, "descricao": "?"})
    session.add(p); await session.commit()
    r = await client.get("/api/v1/pendencias?resolved=false")
    assert len(r.json()) == 1
    r2 = await client.post(f"/api/v1/pendencias/{p.id}/resolve", json={"descricao": "conserto bike"})
    assert r2.status_code == 200
    await session.refresh(p)
    assert p.resolved is True
