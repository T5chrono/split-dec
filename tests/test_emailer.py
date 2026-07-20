"""Invitation email content: user-controlled names must be HTML-escaped,
and nothing about the recipient may reach the logs."""

import io
import logging
import urllib.error
import uuid

import pytest

from _src import emailer
from _src.emailer import invitation_email_content, send_invitation_email

RECIPIENT = "future.user@example.com"
API_KEY = "re_live_supersecretkey"


def test_html_escapes_user_controlled_names():
    content = invitation_email_content(
        '<script>alert(1)</script>',
        '<a href="https://evil.example">Click for a prize</a>',
    )
    assert "<script>" not in content["html"]
    assert "evil.example\">" not in content["html"]
    assert "&lt;script&gt;" in content["html"]
    assert "&lt;a href=" in content["html"]
    # The one legitimate link is ours.
    assert 'href="https://split-dec.vercel.app"' in content["html"]


def test_plain_names_render_unmangled():
    content = invitation_email_content("Tomasz & Ania", "Wyjazd — Zakopane")
    assert "Tomasz &amp; Ania" in content["html"]  # escaped entity in HTML is fine
    assert content["subject"] == "Tomasz & Ania invited you to split expenses on SplitDec"


class TestLogHygiene:
    """Vercel retains function logs; invitation recipients are often not even
    users yet, and Resend echoes the payload back in its error bodies."""

    @pytest.fixture(autouse=True)
    def _capture(self, caplog):
        caplog.set_level(logging.INFO, logger="splitdec.emailer")

    @staticmethod
    def _assert_clean(caplog, correlator):
        text = caplog.text
        assert str(correlator) in text  # the invitation is still traceable
        assert RECIPIENT not in text
        assert "example.com" not in text
        assert API_KEY not in text
        assert "supersecret" not in text

    async def test_skip_without_api_key_logs_no_address(self, caplog, monkeypatch):
        monkeypatch.setattr(emailer, "RESEND_API_KEY", "")
        correlator = uuid.uuid4()
        assert await send_invitation_email(
            RECIPIENT, "Alice", "Trip", correlator=correlator
        ) is False
        self._assert_clean(caplog, correlator)

    async def test_provider_error_body_is_not_logged(self, caplog, monkeypatch):
        body = (
            f'{{"message":"You can only send testing emails to your own address.'
            f' Requested: {RECIPIENT}","key":"{API_KEY}"}}'
        )

        def _raise(payload):
            raise urllib.error.HTTPError(
                "https://api.resend.com/emails", 403, "Forbidden", {}, io.BytesIO(body.encode())
            )

        monkeypatch.setattr(emailer, "RESEND_API_KEY", API_KEY)
        monkeypatch.setattr(emailer, "_post_resend", _raise)
        correlator = uuid.uuid4()
        assert await send_invitation_email(
            RECIPIENT, "Alice", "Trip", correlator=correlator
        ) is False
        self._assert_clean(caplog, correlator)
        assert "403" in caplog.text  # the actionable part survives

    async def test_unexpected_failure_logs_type_only(self, caplog, monkeypatch):
        def _raise(payload):
            raise TimeoutError(f"connection to {RECIPIENT} timed out with {API_KEY}")

        monkeypatch.setattr(emailer, "RESEND_API_KEY", API_KEY)
        monkeypatch.setattr(emailer, "_post_resend", _raise)
        correlator = uuid.uuid4()
        assert await send_invitation_email(
            RECIPIENT, "Alice", "Trip", correlator=correlator
        ) is False
        self._assert_clean(caplog, correlator)
        assert "TimeoutError" in caplog.text
