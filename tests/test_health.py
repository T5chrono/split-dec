async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_db(client, db_engine):
    r = await client.get("/api/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["db_ms"], (int, float))


async def test_health_db_gated_by_probe_key(client, db_engine, monkeypatch):
    monkeypatch.setenv("HEALTH_PROBE_KEY", "s3cret")
    assert (await client.get("/api/health/db")).status_code == 401
    wrong = await client.get("/api/health/db", headers={"X-Health-Key": "nope"})
    assert wrong.status_code == 401
    ok = await client.get("/api/health/db", headers={"X-Health-Key": "s3cret"})
    assert ok.status_code == 200
