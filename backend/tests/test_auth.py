async def test_health_sem_api_key(client):
    r = await client.get("/api/v1/health", headers={"X-API-Key": ""})
    assert r.status_code == 200  # health é público


async def test_rota_protegida_sem_key(client):
    r = await client.get("/api/v1/transactions", headers={"X-API-Key": "errada"})
    assert r.status_code == 401
