async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_health_db_disabled_without_key_outside_development(client, db_engine):
    # No HEALTH_PROBE_KEY and ENV defaults to production: the probe must be
    # off, not open — each call would burn a fresh pooler connection.
    r = await client.get("/api/health/db")
    assert r.status_code == 503


async def test_health_db_open_in_development(client, db_engine, monkeypatch):
    monkeypatch.setenv("ENV", "development")
    r = await client.get("/api/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert isinstance(body["db_ms"], (int, float))


async def test_health_db_stays_closed_when_the_platform_says_hosted(
    client, db_engine, monkeypatch
):
    """ENV=development must not open the probe on a hosted deployment.

    The pure-function matrix lives in test_config.py; this is the one that
    drives the rule through an actual request, so a future refactor that reads
    `os.getenv("ENV")` directly again — as this endpoint used to — fails here
    rather than quietly reopening an unauthenticated database probe in
    production.
    """
    monkeypatch.setenv("ENV", "development")
    for vercel_env in ("production", "preview"):
        monkeypatch.setenv("VERCEL_ENV", vercel_env)
        r = await client.get("/api/health/db")
        assert r.status_code == 503, vercel_env
        # And the refusal says nothing about which variable would open it.
        assert "HEALTH_PROBE_KEY" not in r.text

    # `vercel dev` is the one hosted-looking state that is genuinely local.
    monkeypatch.setenv("VERCEL_ENV", "development")
    assert (await client.get("/api/health/db")).status_code == 200


async def test_health_db_gated_by_probe_key(client, db_engine, monkeypatch):
    monkeypatch.setenv("HEALTH_PROBE_KEY", "s3cret")
    assert (await client.get("/api/health/db")).status_code == 401
    wrong = await client.get("/api/health/db", headers={"X-Health-Key": "nope"})
    assert wrong.status_code == 401
    ok = await client.get("/api/health/db", headers={"X-Health-Key": "s3cret"})
    assert ok.status_code == 200
    # Non-ASCII must be rejected, not crash: secrets.compare_digest refuses
    # non-ASCII str, so the comparison runs on bytes.
    weird = await client.get(
        "/api/health/db", headers={"X-Health-Key": "nöpe".encode("latin-1")}
    )
    assert weird.status_code == 401
