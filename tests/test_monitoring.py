"""The Sentry scrubber, and the delivery it depends on.

Most of this is testing one property: that an event leaving this function
carries no identifier, no credential and no ledger content. The SDK's own
defaults are the adversary — each case below corresponds to something
`sentry-sdk` would have sent if `before_send` were absent.

The last two classes test a different property, and a harder one to notice
going wrong: that an event actually *arrives*. See `flush_on_response`.
"""

import importlib.util
import inspect
import os

import pytest

from _src import monitoring

GROUP_ID = "2b2f0e1c-9a71-4a51-8d0b-6d1c9b0f7e42"
EXPENSE_ID = "8f14e45f-ceea-467a-9c4a-1d7b0c9e2a33"


class TestRedactUrl:
    def test_identifiers_are_replaced(self):
        redacted = monitoring.redact_url(f"https://split-dec.app/api/groups/{GROUP_ID}/expenses")
        assert GROUP_ID not in redacted
        assert redacted == "https://split-dec.app/api/groups/[id]/expenses"

    def test_every_identifier_in_a_path_is_replaced(self):
        redacted = monitoring.redact_url(
            f"https://split-dec.app/api/groups/{GROUP_ID}/members/{EXPENSE_ID}"
        )
        assert redacted == "https://split-dec.app/api/groups/[id]/members/[id]"

    def test_query_string_is_dropped_whole(self):
        # Not filtered per-parameter: the OAuth callback's `?code=` is a live
        # authorization code, and an allow-list is a list someone must maintain.
        redacted = monitoring.redact_url("https://split-dec.app/?code=live-oauth-code")
        assert "code" not in redacted
        assert redacted == "https://split-dec.app/"

    def test_fragment_is_dropped_whole(self):
        redacted = monitoring.redact_url(
            "https://split-dec.app/reset-password#access_token=live-credential"
        )
        assert "access_token" not in redacted
        assert redacted == "https://split-dec.app/reset-password"

    def test_relative_url_stays_relative(self):
        assert monitoring.redact_url(f"/api/expenses/{EXPENSE_ID}") == "/api/expenses/[id]"

    def test_uppercase_identifiers_are_matched_too(self):
        assert monitoring.redact_url(f"/api/groups/{GROUP_ID.upper()}") == "/api/groups/[id]"

    @pytest.mark.parametrize("value", ["", None])
    def test_empty_input_is_returned_unchanged(self, value):
        assert monitoring.redact_url(value or "") == (value or "")


class TestScrubEvent:
    def test_headers_are_allow_listed_not_deny_listed(self):
        """`X-Health-Key` is the case the SDK's own deny-list misses.

        `send_default_pii=False` substitutes Authorization and Cookie, but it
        has never heard of this app's health-probe secret — which is exactly
        why the filter here is an allow-list.
        """
        event = {
            "request": {
                "url": "https://split-dec.app/api/health/db",
                "headers": {
                    "User-Agent": "Mozilla/5.0",
                    "Content-Type": "application/json",
                    "Authorization": "Bearer eyJhbGciOi.live.token",
                    "X-Health-Key": "the-shared-secret",
                    "Idempotency-Key": GROUP_ID,
                    "Referer": f"https://split-dec.app/groups/{GROUP_ID}",
                },
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        headers = scrubbed["request"]["headers"]
        assert set(headers) == {"User-Agent", "Content-Type"}
        assert "the-shared-secret" not in str(scrubbed)
        assert GROUP_ID not in str(scrubbed)

    def test_request_body_never_survives(self):
        """An expense body is the user's ledger, verbatim."""
        event = {
            "request": {
                "url": "https://split-dec.app/api/groups/" + GROUP_ID + "/expenses",
                "query_string": "code=live-oauth-code",
                "cookies": {"sb-access-token": "live"},
                "data": {"description": "Dinner at Marco's", "total_amount": "120.5000"},
                "env": {"REMOTE_ADDR": "203.0.113.7"},
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        request = scrubbed["request"]
        for dropped in ("query_string", "cookies", "data", "env"):
            assert dropped not in request
        assert request["url"] == "https://split-dec.app/api/groups/[id]/expenses"
        assert "Marco" not in str(scrubbed)

    def test_breadcrumb_messages_lose_their_identifiers(self):
        """`emailer.py` logs the invitation id, and log records are breadcrumbs."""
        event = {
            "breadcrumbs": {
                "values": [
                    {
                        "type": "log",
                        "message": f"Resend rejected invitation email {GROUP_ID}: HTTP 429",
                    },
                    {"type": "http", "data": {"url": f"https://split-dec.app/api/groups/{GROUP_ID}"}},
                ]
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        values = scrubbed["breadcrumbs"]["values"]
        assert values[0]["message"] == "Resend rejected invitation email [id]: HTTP 429"
        assert values[1]["data"]["url"] == "https://split-dec.app/api/groups/[id]"

    def test_bare_breadcrumb_list_is_handled(self):
        """Guessing the wrapper shape wrong must not fail open."""
        event = {"breadcrumbs": [{"message": f"touched {GROUP_ID}"}]}
        scrubbed = monitoring.scrub_event(event, {})
        assert scrubbed["breadcrumbs"][0]["message"] == "touched [id]"

    def test_event_without_a_request_is_left_alone(self):
        event = {"exception": {"values": [{"type": "ValueError"}]}}
        assert monitoring.scrub_event(event, {}) == event


class TestScrubMessages:
    """The error's own text — written by Postgres or by a future log call,
    never by us, and missed entirely by the request/breadcrumb hooks."""

    def test_constraint_violation_loses_the_address_it_quotes(self):
        # Verbatim shape of a Postgres unique violation on users.email.
        event = {
            "exception": {
                "values": [
                    {
                        "type": "IntegrityError",
                        "value": (
                            'duplicate key value violates unique constraint "users_email_key"\n'
                            "DETAIL:  Key (email)=(someone@example.com) already exists."
                        ),
                    }
                ]
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        value = scrubbed["exception"]["values"][0]["value"]
        assert "someone@example.com" not in value
        assert "[email]" in value
        # The useful half survives: you can still tell which constraint blew up.
        assert "users_email_key" in value

    def test_identifiers_in_an_exception_message_are_blanked(self):
        event = {
            "exception": {"values": [{"type": "ValueError", "value": f"no group {GROUP_ID}"}]}
        }
        scrubbed = monitoring.scrub_event(event, {})
        assert scrubbed["exception"]["values"][0]["value"] == "no group [id]"

    def test_stack_frames_are_left_alone(self):
        """They name our own files, and locals are off — nothing to redact."""
        frames = {"frames": [{"filename": "/var/task/_src/routers/expenses.py", "lineno": 42}]}
        event = {"exception": {"values": [{"type": "ValueError", "stacktrace": frames}]}}
        scrubbed = monitoring.scrub_event(event, {})
        assert scrubbed["exception"]["values"][0]["stacktrace"] == frames

    def test_logentry_is_scrubbed(self):
        """LoggingIntegration is on by default; integrations=[...] adds to the
        defaults rather than replacing them, so this path is live."""
        event = {
            "logentry": {
                "message": "invite %s failed for %s",
                "formatted": f"invite {GROUP_ID} failed for someone@example.com",
                "params": [GROUP_ID, "someone@example.com"],
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        assert scrubbed["logentry"]["formatted"] == "invite [id] failed for [email]"
        assert scrubbed["logentry"]["params"] == ["[id]", "[email]"]

    def test_capture_message_text_is_scrubbed(self):
        event = {"message": f"group {GROUP_ID} is wedged"}
        assert monitoring.scrub_event(event, {})["message"] == "group [id] is wedged"

    def test_a_breadcrumb_is_held_to_the_same_standard_as_an_event(self):
        """The quieter door to the same text.

        `logger.warning` becomes a breadcrumb where `logger.error` becomes an
        event body. Scrubbing only the loud one leaves the level of a log call
        deciding whether an address ships.
        """
        event = {
            "breadcrumbs": {
                "values": [{"type": "log", "message": "invite to someone@example.com failed"}]
            }
        }
        scrubbed = monitoring.scrub_event(event, {})
        assert scrubbed["breadcrumbs"]["values"][0]["message"] == "invite to [email] failed"


def test_init_is_a_no_op_without_a_dsn(monkeypatch):
    """The absence of a DSN is the only off switch, so it has to hold.

    If this ever regressed, the test suite itself would start posting events.
    """
    monkeypatch.setattr(monitoring, "SENTRY_DSN", "")
    called = False

    def explode(**_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(monitoring.sentry_sdk, "init", explode)
    monitoring.init_monitoring()
    assert called is False


def test_release_health_is_off_and_keep_alive_is_on(monkeypatch):
    """Two init options that cost nothing to keep and mattered to get right.

    Sessions are the traffic that used to fill the production log with retry
    warnings: one per request, uploaded by a background thread that the
    platform freezes mid-send, for a feature nothing here reads. `keep_alive`
    is asserted so that removing it stays a deliberate act — it does not fix
    what it was added for, but it is still correct for a connection idling
    while the process runs.
    """
    monkeypatch.setattr(
        monitoring, "SENTRY_DSN", "https://k@o0.ingest.de.sentry.io/1"
    )
    options: dict = {}
    monkeypatch.setattr(
        monitoring.sentry_sdk, "init", lambda **kwargs: options.update(kwargs)
    )
    monitoring.init_monitoring()
    assert options["auto_session_tracking"] is False
    assert options["keep_alive"] is True


class TestFlushOnResponse:
    """Does a captured event leave before the platform freezes the instance?"""

    @pytest.fixture
    def flushes(self, monkeypatch):
        recorded: list[float] = []
        monkeypatch.setattr(
            monitoring.sentry_sdk, "flush", lambda timeout: recorded.append(timeout)
        )
        return recorded

    async def test_a_request_that_captured_nothing_does_not_wait(self, flushes):
        """Nearly every request. It must cost an integer comparison, not a round trip."""

        async def inner(scope, receive, send):
            return None

        await monitoring.flush_on_response(inner)({"type": "http"}, None, None)
        assert flushes == []

    async def test_a_captured_event_is_flushed(self, flushes):
        async def inner(scope, receive, send):
            monitoring.scrub_event({"message": "boom"}, {})

        await monitoring.flush_on_response(inner)({"type": "http"}, None, None)
        assert flushes == [monitoring.FLUSH_TIMEOUT]

    async def test_an_unhandled_exception_is_flushed_and_still_raised(self, flushes):
        """The case the wrapper exists for.

        `SentryAsgiMiddleware` captures on the way out and re-raises, so by the
        time the exception reaches this wrapper the event is queued. Flushing
        in `finally` is what gets it sent; re-raising is what keeps the 500.
        """

        async def inner(scope, receive, send):
            monitoring.scrub_event({"message": "boom"}, {})
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await monitoring.flush_on_response(inner)({"type": "http"}, None, None)
        assert flushes == [monitoring.FLUSH_TIMEOUT]

    async def test_non_http_scopes_pass_straight_through(self, flushes):
        """Lifespan runs once per instance and has no reply to hold up."""
        seen: list[str] = []

        async def inner(scope, receive, send):
            monitoring.scrub_event({"message": "boom"}, {})
            seen.append(scope["type"])

        await monitoring.flush_on_response(inner)({"type": "lifespan"}, None, None)
        assert seen == ["lifespan"]
        assert flushes == []


def test_the_vercel_entrypoint_is_shaped_like_an_asgi_app():
    """Vercel decides ASGI vs WSGI by shape, and gets it wrong silently.

    `vercel_runtime/resolver.py` asks two questions: is the object a coroutine
    function (or is its `__call__` one), and how many *required positional*
    parameters does it take. Three means ASGI, two means WSGI, anything else is
    a build error. So giving `flush_on_response`'s wrapper a default argument
    would hand the app to the platform as WSGI, which fails per request at
    runtime rather than once at build time — exactly the kind of break a test
    suite that only ever drives `_src.main.app` would not see.
    """
    path = os.path.join(os.path.dirname(__file__), "..", "api", "index.py")
    spec = importlib.util.spec_from_file_location("vercel_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert inspect.iscoroutinefunction(module.app)
    required = [
        parameter
        for parameter in inspect.signature(module.app).parameters.values()
        if parameter.default is inspect.Parameter.empty
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    assert len(required) == 3
