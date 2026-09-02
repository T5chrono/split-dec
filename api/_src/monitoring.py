"""Error monitoring for the API function (Sentry), and the redaction it needs.

The browser half of this lives in `src/lib/monitoring.ts` and the reasoning is
the same: a crash reporter reports *context*, and its defaults collect the
things this codebase works hardest to keep out of logs. On the server the
specific hazards are different from the browser's, and worse:

  - **Local variables.** `sentry-sdk` attaches every stack frame's locals by
    default. One frame up from any database error sits `DATABASE_URL` with the
    pooler password in it; inside `auth.py` sits the caller's raw bearer token;
    inside `invitations.py`, an email address and its `recipient_key` hash.
    A stack trace here is a credential dump unless `include_local_variables` is
    off, and it is the single most important line in `init()` below.
  - **Request bodies.** An expense POST *is* the user's data — description,
    amount, who paid, how it splits. `max_request_body_size="never"`.
  - **Headers.** `send_default_pii=False` already substitutes `Authorization`
    and `Cookie` (`SENSITIVE_HEADERS` in the SDK), but that is a deny-list, and
    the header it does not know about is `X-Health-Key` — the shared secret for
    `/api/health/db`. So headers are allow-listed here instead: a deny-list is
    wrong by default for anything a future endpoint might add.
  - **URLs.** `/api/groups/<uuid>/expenses` names a group; `?` and `#` never
    carry a credential on this side the way they do in the browser, but they
    are dropped anyway rather than reasoned about per endpoint.
  - **The error's own message**, which is the one nothing above covers and the
    one we do not write. A unique-violation on `users.email` reaches Sentry as
    `DETAIL: Key (email)=(someone@example.com) already exists`. Same for
    `logentry`, the field `LoggingIntegration` fills from any `logger.error()`
    — that integration is on by default, and `integrations=[...]` adds to the
    defaults rather than replacing them, so it is live whether or not this
    codebase uses it yet.

`transaction` is left alone deliberately: the FastAPI integration sets it to the
*route pattern* (`/api/groups/{group_id}/expenses`), which is already folded and
is what makes the issue stream group properly.

Identifiers are matched by shape rather than by route, exactly as in the browser
module — every id in `models.py` is a UUID, so one pattern covers every current
route and every future one. Note this is a different contract from `fold_route`
in `routers/reports.py`, which folds *named* patterns because its output has to
line up bucket-for-bucket with `insightsRoute` in the frontend. Nothing here has
to line up with anything, so it can afford the stricter rule.
"""

import re
from typing import Any
from urllib.parse import urlsplit

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from .config import SENTRY_DSN, SENTRY_ENVIRONMENT, SENTRY_RELEASE

_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

# Free text can carry the other identifier this app holds. Postgres puts it
# there without being asked: a unique-violation on `users.email` arrives as
# `DETAIL: Key (email)=(someone@example.com) already exists`, and that string is
# the exception's own message rather than anything this module chose to send.
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Everything a stack trace is actually diagnosed with, and nothing else.
# Allow-list rather than deny-list: the next header this API reads should not
# reach a third party because nobody remembered to come back and exclude it.
_ALLOWED_HEADERS = frozenset({"user-agent", "content-type", "content-length", "accept"})


def redact_ids(text: str) -> str:
    """Every UUID in a string replaced by a placeholder."""
    return _UUID.sub("[id]", text)


def redact_message(text: str) -> str:
    """Free text with both identifier shapes blanked.

    Separate from `redact_ids` because the inputs are different in kind: that
    one folds URL *paths*, where an email can never appear, while this one
    handles text somebody else wrote — an exception message, a log record — and
    has to assume anything the app holds could be embedded in it.
    """
    return _EMAIL.sub("[email]", _UUID.sub("[id]", text))


def redact_url(url: str) -> str:
    """A URL reduced to scheme, host and path, with identifiers blanked.

    Query and fragment are dropped whole rather than filtered, for the reason
    the browser module gives: an allow-list of safe parameters is a list that
    has to be maintained against every future endpoint, and getting it wrong
    once is not recoverable — the event has already been sent.
    """
    if not url:
        return url
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[redacted]"
    path = redact_ids(parts.path)
    if not parts.scheme or not parts.netloc:
        return path or "[redacted]"
    return f"{parts.scheme}://{parts.netloc}{path}"


def _scrub_request(request: dict[str, Any]) -> dict[str, Any]:
    scrubbed = dict(request)
    url = scrubbed.get("url")
    if isinstance(url, str):
        scrubbed["url"] = redact_url(url)
    for key in ("query_string", "cookies", "data", "env"):
        scrubbed.pop(key, None)
    headers = scrubbed.get("headers")
    if isinstance(headers, dict):
        scrubbed["headers"] = {
            k: v for k, v in headers.items() if k.lower() in _ALLOWED_HEADERS
        }
    return scrubbed


def _scrub_breadcrumbs(values: list[Any]) -> list[Any]:
    """Identifiers out of breadcrumb text.

    Log records become breadcrumbs, and `emailer.py` logs the invitation id as
    its correlator — deliberately, because it is the one thing there that is
    *not* an email address. It belongs in Vercel's own logs; it does not belong
    in a third party's.
    """
    scrubbed = []
    for crumb in values:
        if not isinstance(crumb, dict):
            scrubbed.append(crumb)
            continue
        crumb = dict(crumb)
        message = crumb.get("message")
        if isinstance(message, str):
            # `redact_message`, not `redact_ids`: this is the same formatted
            # log text that reaches `logentry` when the level is ERROR, just
            # arriving by the quieter door. Holding the two paths to different
            # standards is how a future `logger.warning(f"... {email}")` gets
            # through a module whose whole claim is that nothing does.
            crumb["message"] = redact_message(message)
        data = crumb.get("data")
        if isinstance(data, dict) and isinstance(data.get("url"), str):
            crumb["data"] = {**data, "url": redact_url(data["url"])}
        scrubbed.append(crumb)
    return scrubbed


def _scrub_exception(exception: dict[str, Any]) -> dict[str, Any]:
    """The error's own message.

    The most likely leak on this side, and the one every other hook here
    misses: a database error's text is written by Postgres, not by us, and a
    constraint violation quotes the offending row back verbatim. Stack frames
    are left alone — they are our own file and function names, and with
    `include_local_variables=False` they carry no values.
    """
    values = exception.get("values")
    if not isinstance(values, list):
        return exception
    scrubbed = []
    for value in values:
        if isinstance(value, dict) and isinstance(value.get("value"), str):
            value = {**value, "value": redact_message(value["value"])}
        scrubbed.append(value)
    return {**exception, "values": scrubbed}


def _scrub_logentry(logentry: dict[str, Any]) -> dict[str, Any]:
    """A log record promoted to an event.

    `LoggingIntegration` is on by default and `integrations=[...]` *adds* to the
    defaults rather than replacing them, so every `logger.error()` in this
    codebase's future becomes an event whose body is this field. There are none
    today; this exists so that the first one is not also the first leak.
    """
    scrubbed = dict(logentry)
    for key in ("message", "formatted"):
        if isinstance(scrubbed.get(key), str):
            scrubbed[key] = redact_message(scrubbed[key])
    params = scrubbed.get("params")
    if isinstance(params, (list, tuple)):
        scrubbed["params"] = [
            redact_message(p) if isinstance(p, str) else p for p in params
        ]
    return scrubbed


def scrub_event(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
    """Last gate before an event leaves the function."""
    request = event.get("request")
    if isinstance(request, dict):
        event["request"] = _scrub_request(request)

    exception = event.get("exception")
    if isinstance(exception, dict):
        event["exception"] = _scrub_exception(exception)

    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        event["logentry"] = _scrub_logentry(logentry)

    # `capture_message` puts its text here rather than in `logentry`.
    if isinstance(event.get("message"), str):
        event["message"] = redact_message(event["message"])

    breadcrumbs = event.get("breadcrumbs")
    # The SDK wraps these as {"values": [...]}; older shapes hand back a bare
    # list. Both are handled because guessing wrong here fails open.
    if isinstance(breadcrumbs, dict) and isinstance(breadcrumbs.get("values"), list):
        event["breadcrumbs"] = {
            **breadcrumbs,
            "values": _scrub_breadcrumbs(breadcrumbs["values"]),
        }
    elif isinstance(breadcrumbs, list):
        event["breadcrumbs"] = _scrub_breadcrumbs(breadcrumbs)

    return event


def init_monitoring() -> None:
    """Start error reporting, if this deployment was given somewhere to report.

    No DSN means no SDK — that is how the test suite and a local uvicorn stay
    silent without a second flag to keep in sync with the first.

    Called at import time from `main.py`, before the FastAPI app is constructed:
    the Starlette integration patches middleware and route handling on the
    class, so an app built first would come out unpatched.
    """
    if not SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE or None,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        # Errors only. Tracing would sample every request through a function
        # that is already pinned next to its database for latency; the number
        # it would report is one Vercel already shows.
        traces_sample_rate=0.0,
        # No IP address, no cookies, no `Authorization`. See the module docstring
        # for why this is necessary but nowhere near sufficient on its own.
        send_default_pii=False,
        # The important one. Without it every database error carries the pooler
        # password and every auth error carries a live bearer token.
        include_local_variables=False,
        # An expense or settlement body is the user's ledger, verbatim.
        max_request_body_size="never",
        before_send=scrub_event,
    )
