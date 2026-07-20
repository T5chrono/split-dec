"""Optional outbound email via Resend (https://resend.com).

Sending is best-effort: without RESEND_API_KEY (or on any failure) the
invitation is still recorded and the frontend offers a mailto draft instead.
"""

import asyncio
import html
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("splitdec.emailer")

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "SplitDec <onboarding@resend.dev>")
APP_URL = os.getenv("APP_URL", "https://split-dec.vercel.app")


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


def invitation_email_content(inviter_name: str, group_name: str) -> dict[str, str]:
    """Subject + HTML body. Inviter and group names are user-controlled and
    MUST be escaped — otherwise a group named `<a href=...>` injects markup
    into an official SplitDec email. APP_URL is deployment config, not user
    input."""
    safe_inviter = html.escape(inviter_name)
    safe_group = html.escape(group_name)
    return {
        # Subject is plain text (no HTML rendering), so no entity escaping —
        # the JSON transport already prevents header injection.
        "subject": f"{inviter_name} invited you to split expenses on SplitDec",
        "html": (
            f"<p><strong>{safe_inviter}</strong> invited you to join the group "
            f"<strong>{safe_group}</strong> on SplitDec — an app for splitting "
            f"expenses with friends.</p>"
            f'<p><a href="{html.escape(APP_URL, quote=True)}">Sign in</a> '
            f"using this email address and the invitation will be waiting for you.</p>"
        ),
    }


async def send_invitation_email(
    to: str, inviter_name: str, group_name: str, *, correlator: object
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
    payload = {"from": RESEND_FROM, "to": [to], **invitation_email_content(inviter_name, group_name)}
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
