from datetime import date


async def test_lista_previstos(client, session):
    from app.core.auth import get_single_user
    from app.models.models import ScheduledOrigin, ScheduledStatus, ScheduledTransaction
    user = await get_single_user(session)
    session.add(ScheduledTransaction(
        user_id=user.id, due_date=date(2026, 8, 10), description="Parcela 3/12 Notebook",
        amount=-350, origin=ScheduledOrigin.ofx_futuro, status=ScheduledStatus.previsto))
    session.add(ScheduledTransaction(
        user_id=user.id, due_date=date(2026, 7, 1), description="Já efetivado",
        amount=-100, origin=ScheduledOrigin.ofx_futuro, status=ScheduledStatus.efetivado))
    await session.commit()

    r = await client.get("/api/v1/scheduled?status=previsto")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["description"] == "Parcela 3/12 Notebook"
