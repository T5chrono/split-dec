"""Optional outbound email via Resend (https://resend.com).

Sending is best-effort: without RESEND_API_KEY (or on any failure) the
invitation is still recorded and the frontend offers a mailto draft instead.
"""

import asyncio
import html
import json
import logging
import os
import unicodedata
import urllib.error
import urllib.request

logger = logging.getLogger("splitdec.emailer")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "SplitDec <onboarding@resend.dev>")
# The apex, not the vercel.app alias: that host is noindex and, more to the
# point, an installed PWA pins the origin it was installed from, so a link that
# opens the alias strands the reader outside their own installation.
APP_URL = os.getenv("APP_URL", "https://split-dec.app")

# What the subject line is allowed to be, in bytes of UTF-8. Not an RFC limit
# and not a Resend one — neither is verified here. It is our own bound, so that
# a display name someone typed cannot decide how long an outbound header is.
# 200 leaves the whole sentence intact for any name a person actually has.
MAX_SUBJECT_BYTES = 200

SUBJECT_SUFFIX = " invited you to split expenses on SplitDec"

# The address src/lib/legal.ts names as the contact point. Duplicated across
# the language boundary rather than shared, which is unavoidable; if one moves,
# move the other.
CONTACT_EMAIL = "privacy@split-dec.app"
# Valid with no secret, no endpoint and no stored row (RFC 2369), so it is what
# an unconfigured deployment still offers. It reaches a person rather than a
# mechanism, which is exactly why it is the fallback and not the plan.
UNSUBSCRIBE_MAILTO = f"mailto:{CONTACT_EMAIL}?subject=Unsubscribe"

# Stand-in for a name that normalizes away to nothing — an inviter called
# a zero-width space (U+200B) would otherwise open the subject with one.
ANONYMOUS_INVITER = "Someone"


def _subject_safe(name: str) -> str:
    """A display name reduced to one line of printable text.

    The subject reaches Resend as a JSON string, so this is not a fix for a
    proven header injection — the provider builds the MIME header and how it
    encodes what we hand it is not something this codebase can see. It is a
    bound we can state: whatever the provider does, the value it is given holds
    no control characters, no line or paragraph separators, and no bidi
    overrides that would let a name reorder the sentence around it. Defence in
    depth, and cheap.

    Categories, not a character list: Cc (control), Cf (format — where the
    RTL/LTR overrides live), Zl and Zp (line and paragraph separators) become
    spaces, then runs of whitespace collapse to one. `str.split()` is
    Unicode-aware, so U+2028 and U+00A0 collapse with the ASCII ones.

    The stored name and the HTML body are untouched: the body is escaped, and
    the ledger's copy of what someone called themselves is not this function's
    business.
    """
    cleaned = "".join(
        " " if unicodedata.category(ch) in {"Cc", "Cf", "Zl", "Zp"} else ch
        for ch in name or ""
    )
    return " ".join(cleaned.split()) or ANONYMOUS_INVITER


def _bounded(text: str, limit: int) -> str:
    """`text` cut to at most `limit` UTF-8 bytes, never mid-character.

    Decoding the truncated bytes with `errors="ignore"` drops a partial
    character rather than emitting a replacement one. A cut can still land
    inside a grapheme cluster — between a base character and its combining
    accent, or inside an emoji sequence — which is a cosmetic loss on a name
    long enough to have needed cutting at all.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[:limit].decode("utf-8", "ignore").rstrip()


def _post_resend(payload: dict) -> None:
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Resend returned {resp.status}")


def unsubscribe_footer(token: str | None) -> str:
    """The line that tells a stranger how to make this stop.

    Every invitation goes to an address that may never have heard of SplitDec,
    so there is always a way out: the signed link when the deployment has a
    secret to sign with, and the contact address when it does not. The token is
    base64url and needs no escaping, but goes through the same escape as
    APP_URL so the rule at this boundary stays "everything interpolated into an
    href is escaped" rather than a judgement per value.
    """
    if token:
        url = html.escape(f"{APP_URL}/unsubscribe?token={token}", quote=True)
        label = "Don't want invitations from SplitDec?"
        return (
            f'<p style="font-size:12px"><a href="{url}">{label}</a> '
            f"You will still see the invitation if you sign up.</p>"
        )
    return (
        f'<p style="font-size:12px">To stop receiving invitations from SplitDec, '
        f'write to <a href="{html.escape(UNSUBSCRIBE_MAILTO, quote=True)}">'
        f"{CONTACT_EMAIL}</a>.</p>"
    )


def invitation_email_content(
    inviter_name: str, group_name: str, unsubscribe_token: str | None = None
) -> dict[str, str]:
    """Subject + HTML body. Inviter and group names are user-controlled and
    MUST be escaped — otherwise a group named `<a href=...>` injects markup
    into an official SplitDec email. APP_URL is deployment config, not user
    input."""
    safe_inviter = html.escape(inviter_name)
    safe_group = html.escape(group_name)
    # The name is bounded so the fixed half of the sentence survives: cutting
    # the whole subject at the limit would leave a long name followed by a
    # truncated explanation of why the reader got the mail.
    subject_name = _bounded(
        _subject_safe(inviter_name),
        MAX_SUBJECT_BYTES - len(SUBJECT_SUFFIX.encode("utf-8")),
    )
    return {
        # Plain text, so no entity escaping — but normalized and bounded, see
        # `_subject_safe`. The HTML body keeps the name as given (escaped).
        "subject": f"{subject_name}{SUBJECT_SUFFIX}",
        "html": (
            f"<p><strong>{safe_inviter}</strong> invited you to join the group "
            f"<strong>{safe_group}</strong> on SplitDec — an app for splitting "
            f"expenses with friends.</p>"
            f'<p><a href="{html.escape(APP_URL, quote=True)}">Sign in</a> '
            f"using this email address and the invitation will be waiting for you.</p>"
            + unsubscribe_footer(unsubscribe_token)
        ),
    }


def unsubscribe_headers(token: str | None) -> dict[str, str]:
    """`List-Unsubscribe` and, where we can honour it, one-click.

    This is the half that matters most and is easiest to forget: a mail client
    only shows its own unsubscribe button when the message carries these, and
    bulk-sender rules at the large providers have expected them since 2024. So
    they protect the sending domain as much as the reader.

    `List-Unsubscribe-Post` (RFC 8058) means the provider POSTs the https URL
    itself, with no human and no page. That is why the API route is POST-only
    and why the token alone authorizes it — see routers/unsubscribe.py. The
    mailto is listed alongside for clients that only understand that form, and
    is all a deployment without a secret can offer.
    """
    if not token:
        return {"List-Unsubscribe": f"<{UNSUBSCRIBE_MAILTO}>"}
    return {
        "List-Unsubscribe": f"<{APP_URL}/api/unsubscribe?token={token}>, <{UNSUBSCRIBE_MAILTO}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


async def send_invitation_email(
    to: str,
    inviter_name: str,
    group_name: str,
    *,
    correlator: object,
    unsubscribe_token: str | None = None,
) -> bool:
    """Returns True only if an email was actually handed to the provider.

    `correlator` (the invitation id) is what gets logged — never the
    recipient address. Log lines end up in Vercel's retained function logs,
    which is not a place to accumulate the email addresses of people who are
    not even users yet. Provider responses are logged as a status code only:
    Resend echoes the payload (recipient, sender, sometimes the key prefix)
    in its error bodies.
    """
    if not RESEND_API_KEY:
        logger.info("RESEND_API_KEY unset; skipping invitation email %s", correlator)
        return False
    payload = {
        "from": RESEND_FROM,
        "to": [to],
        "headers": unsubscribe_headers(unsubscribe_token),
        **invitation_email_content(inviter_name, group_name, unsubscribe_token),
    }
    try:
        await asyncio.to_thread(_post_resend, payload)
        return True
    except urllib.error.HTTPError as e:
        # The status code alone distinguishes the cases worth acting on
        # (403 sandbox restriction, 422 bad sender, 429 provider throttle).
        logger.warning("Resend rejected invitation email %s: HTTP %s", correlator, e.code)
        return False
    except Exception as e:  # noqa: BLE001 — best-effort; must not fail the request
        logger.warning(
            "Failed to send invitation email %s: %s", correlator, type(e).__name__
        )
        return False
