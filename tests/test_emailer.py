"""Invitation email content: user-controlled names must be HTML-escaped,
and nothing about the recipient may reach the logs."""

import io
import logging
import unicodedata
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
    # The one legitimate link is ours, and it names the canonical origin: an
    # installed PWA pins the origin it was installed from, so an invitation
    # opening the vercel.app alias lands the reader outside their own app.
    assert f'href="{emailer.APP_URL}"' in content["html"]
    assert emailer.APP_URL == "https://split-dec.app"


def test_plain_names_render_unmangled():
    content = invitation_email_content("Tomasz & Ania", "Wyjazd — Zakopane")
    assert "Tomasz &amp; Ania" in content["html"]  # escaped entity in HTML is fine
    assert content["subject"] == "Tomasz & Ania invited you to split expenses on SplitDec"


class TestSubjectContract:
    """The subject is a derived value handed to a provider that builds the MIME
    header for us.

    No header injection through Resend is demonstrated — the payload is JSON and
    what the provider does with it downstream is not visible from here. What is
    pinned is the contract on our side: one line, no control characters, no bidi
    overrides, bounded length. These are our limits, not claimed RFC or Resend
    requirements.
    """

    @staticmethod
    def _subject(name: str) -> str:
        return invitation_email_content(name, "Trip")["subject"]

    def test_an_ordinary_name_is_untouched(self):
        assert self._subject("Tomasz Giela") == (
            "Tomasz Giela invited you to split expenses on SplitDec"
        )

    def test_benign_unicode_names_survive(self):
        """Normalization must not mangle a name somebody actually has."""
        for name in ("Zażółć Gęślą", "Ünal Öztürk", "李雷", "Ana-María O'Brien"):
            assert self._subject(name).startswith(name + " invited you")

    @pytest.mark.parametrize(
        "raw",
        [
            'Alice\r\nBcc: victim@example.com',
            'Alice\nSubject: something else',
            'Alice\x00\x07',
            'Alice\x0b\x0c',
            'Alice\u2028Bob',  # line separator
            'Alice\u2029Bob',  # paragraph separator
            'Alice\u202eBob',  # right-to-left override
            'Alice\u200bBob',  # zero-width space
        ],
        ids=['crlf', 'lf', 'nul', 'vtab', 'u2028', 'u2029', 'rtl-override', 'zwsp'],
    )
    def test_control_characters_never_reach_the_subject(self, raw):
        subject = self._subject(raw)
        assert not any(unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} for ch in subject)
        assert not any(ch in subject for ch in '\n\r')
        assert subject.endswith(" invited you to split expenses on SplitDec")

    def test_a_name_that_normalizes_to_nothing_gets_a_stand_in(self):
        for empty in ('', '   ', '\u200b\u200b', '\n\t'):
            assert self._subject(empty) == (
                "Someone invited you to split expenses on SplitDec"
            )

    def test_the_subject_is_bounded_and_keeps_the_whole_sentence(self):
        subject = self._subject("Ą" * 500)
        assert len(subject.encode("utf-8")) <= emailer.MAX_SUBJECT_BYTES
        assert subject.endswith(emailer.SUBJECT_SUFFIX)
        # Cut on a character boundary, not mid-sequence.
        assert subject.encode("utf-8").decode("utf-8") == subject

    def test_the_html_body_still_carries_the_name_as_given(self):
        """Only the subject is normalized. The body escapes instead, and the
        stored name is not this function's business."""
        name = 'Alice\u200bBob'
        content = invitation_email_content(name, "Trip")
        assert name in content["html"]


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
