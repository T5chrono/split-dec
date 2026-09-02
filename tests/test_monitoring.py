"""The Sentry scrubber.

Everything here is testing one property: that an event leaving this function
carries no identifier, no credential and no ledger content. The SDK's own
defaults are the adversary — each case below corresponds to something
`sentry-sdk` would have sent if `before_send` were absent.
"""

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
