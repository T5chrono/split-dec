import pytest

from _src import main


def _handshake(result: str):
    async def _probe(host: str, timeout: float = 5.0) -> str:
        return result

    return _probe


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


class TestSentryProbe:
    """`/api/health/sentry` — the only way to find out whether error reporting
    from this function actually works.

    Nothing else can tell you. The SDK's transport records a failed delivery
    and re-raises into `capture_internal_exceptions()`, which swallows it, so
    it writes no log line when it gives up: a project that has never received
    anything from production reads exactly like an app that has never thrown.
    """

    KEY = {"X-Health-Key": "s3cret"}

    @pytest.fixture(autouse=True)
    def _keyed(self, monkeypatch):
        monkeypatch.setenv("HEALTH_PROBE_KEY", "s3cret")

    @pytest.fixture
    def sent(self, monkeypatch):
        """A configured DSN and a stubbed SDK, so no test opens a socket."""
        calls: dict[str, object] = {"flushed": False}
        monkeypatch.setattr(main, "SENTRY_DSN", "https://k@o1.ingest.de.sentry.io/2")
        monkeypatch.setattr(
            main.sentry_sdk, "capture_message", lambda *a, **k: "deadbeef"
        )
        monkeypatch.setattr(
            main.sentry_sdk,
            "flush",
            lambda *a, **k: calls.__setitem__("flushed", True),
        )
        # Stands in for `LoggingIntegration` promoting the `logger.error`
        # below it into an event of its own. A distinct id is the working
        # case; the broken case is covered separately, and it is the one the
        # field exists for.
        monkeypatch.setattr(main.sentry_sdk, "last_event_id", lambda: "cafef00d")
        return calls

    async def test_it_is_gated_like_the_database_probe(self, client, monkeypatch):
        assert (await client.get("/api/health/sentry")).status_code == 401
        bad = await client.get("/api/health/sentry", headers={"X-Health-Key": "no"})
        assert bad.status_code == 401

    async def test_an_unconfigured_key_closes_it_rather_than_opening_it(
        self, client, monkeypatch
    ):
        """It names the ingest host and returns raw connection errors, so the
        missing-key case must fail closed exactly like the database probe."""
        monkeypatch.delenv("HEALTH_PROBE_KEY", raising=False)
        r = await client.get("/api/health/sentry")
        assert r.status_code == 503
        assert "HEALTH_PROBE_KEY" not in r.text

    async def test_no_dsn_is_reported_rather_than_guessed(self, client, monkeypatch):
        """Not an error: no DSN is how dev, CI and vitest stay out of the issue
        stream, so the honest answer is that nothing is configured to test."""
        monkeypatch.setattr(main, "SENTRY_DSN", "")
        r = await client.get("/api/health/sentry", headers=self.KEY)
        assert r.status_code == 200
        assert r.json() == {
            "dsn_configured": False,
            "ingest_host": None,
            "tls": None,
            "event_id": None,
            "logentry_event_id": None,
        }

    async def test_it_reports_the_handshake_and_the_event(
        self, client, monkeypatch, sent
    ):
        monkeypatch.setattr(main, "ingest_handshake", _handshake("ok"))
        r = await client.get("/api/health/sentry", headers=self.KEY)
        body = r.json()
        assert body["ingest_host"] == "o1.ingest.de.sentry.io"
        assert body["tls"] == "ok"
        assert body["event_id"] == "deadbeef"

    async def test_a_broken_handshake_is_the_answer_not_an_error(
        self, client, monkeypatch, sent
    ):
        """The failure this route was built to catch, verbatim rather than
        folded into a status code — `SSLEOFError` against `/envelope/` is what
        production logged for months while reporting silently delivered
        nothing."""
        monkeypatch.setattr(main, "ingest_handshake", _handshake("SSLEOFError: EOF"))
        r = await client.get("/api/health/sentry", headers=self.KEY)
        assert r.status_code == 200
        assert r.json()["tls"] == "SSLEOFError: EOF"

    async def test_the_event_is_flushed_before_answering(
        self, client, monkeypatch, sent
    ):
        """Without this the answer is worthless: the SDK sends on a background
        worker, and the platform can freeze the instance the moment the
        response is written — taking the envelope with it."""
        monkeypatch.setattr(main, "ingest_handshake", _handshake("ok"))
        await client.get("/api/health/sentry", headers=self.KEY)
        assert sent["flushed"] is True


class TestLogentryProbe:
    """The half of the probe that matches what the app actually does.

    Every alert this codebase raises is a `logger.error` — the three Resend
    failures, `monitoring.alert`, a flush that gave up — and each reaches
    Sentry only because `LoggingIntegration` is a *default* integration that
    promotes ERROR into an event. Nothing in `init_monitoring` configures it,
    so the assumption is invisible, and until this probe existed the route
    answered "reporting works" having exercised `capture_message` and nothing
    else: a path no alert in the app takes.
    """

    KEY = {"X-Health-Key": "s3cret"}

    @pytest.fixture(autouse=True)
    def _keyed(self, monkeypatch):
        monkeypatch.setenv("HEALTH_PROBE_KEY", "s3cret")
        monkeypatch.setattr(main, "SENTRY_DSN", "https://k@o1.ingest.de.sentry.io/2")
        monkeypatch.setattr(main, "ingest_handshake", _handshake("ok"))
        monkeypatch.setattr(main.sentry_sdk, "flush", lambda *a, **k: None)
        monkeypatch.setattr(
            main.sentry_sdk, "capture_message", lambda *a, **k: "deadbeef"
        )

    async def test_a_promoted_log_call_is_reported_as_its_own_event(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(main.sentry_sdk, "last_event_id", lambda: "cafef00d")
        body = (await client.get("/api/health/sentry", headers=self.KEY)).json()
        assert body["event_id"] == "deadbeef"
        assert body["logentry_event_id"] == "cafef00d"

    async def test_an_unpromoted_log_call_reads_as_null_not_as_success(
        self, client, monkeypatch
    ):
        """The whole point of comparing rather than trusting `last_event_id`.

        With the promotion off, the logger call captures nothing, so the scope
        still holds the id from `capture_message` two lines up. Returned
        blindly it would report the message probe's id as proof that the
        logentry path works — a false success on exactly the question the
        probe was added to answer.
        """
        monkeypatch.setattr(main.sentry_sdk, "last_event_id", lambda: "deadbeef")
        body = (await client.get("/api/health/sentry", headers=self.KEY)).json()
        assert body["event_id"] == "deadbeef"
        assert body["logentry_event_id"] is None

    async def test_it_survives_an_sdk_that_has_no_event_to_report(
        self, client, monkeypatch
    ):
        """No init, no scope, no last event — must answer, not raise."""
        monkeypatch.setattr(main.sentry_sdk, "last_event_id", lambda: None)
        r = await client.get("/api/health/sentry", headers=self.KEY)
        assert r.status_code == 200
        assert r.json()["logentry_event_id"] is None
