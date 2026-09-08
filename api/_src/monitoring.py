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

import asyncio
import re
import threading
from collections.abc import Awaitable, Callable
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

# How long a request will wait for its own event to reach Sentry before giving
# up and answering anyway. The number that makes this necessary is the
# transport's own `HttpTransport.TIMEOUT = 30`: an unbounded flush would let a
# slow or unreachable ingest host add half a minute to a request that has
# already produced its response.
FLUSH_TIMEOUT = 2.0

# Counts events that survived `scrub_event`. `flush_on_response` reads it
# before and after a request to decide whether there is anything to wait for --
# the overwhelming majority of requests capture nothing and must not pay for a
# flush.
#
# Behind a lock rather than a bare `+= 1`, which is three bytecodes and can
# therefore lose an increment: `before_send` runs on whichever thread called
# `capture_event`, and that is not always the request's own. The lock is
# uncontended on every request that does not report something.
_capture_lock = threading.Lock()
_capture_count = 0


def _note_capture() -> None:
    global _capture_count
    with _capture_lock:
        _capture_count += 1


def captures_seen() -> int:
    """How many events have been handed to the transport since this cold start."""
    with _capture_lock:
        return _capture_count



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

    # Last thing before the event is queued, so `flush_on_response` knows this
    # request produced something worth waiting for. Counted here rather than at
    # the top: an event this function decided to drop is not one to flush for.
    _note_capture()
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
        # Release health, off. The SDK opens a session for every request
        # (`track_session` in the ASGI integration) and a background thread
        # posts the aggregates every 60 seconds. Nothing reads them — this
        # deployment is errors-only — and each one is a send that begins as the
        # invocation ends, which is the window `flush_on_response` exists to
        # close. Until this was turned off, the uptime monitor's five-minute
        # ping of `/api/health` was the app's main source of Sentry traffic,
        # and that traffic was the app's main source of log warnings: a session
        # nobody would read, failing to upload, once every few minutes.
        #
        # `track_session` is documented as "a no-op context manager if session
        # tracking is not enabled", so this removes the session and nothing
        # else. Errors are unaffected.
        auto_session_tracking=False,
        # TCP keep-alive on the connection to the ingest host: SO_KEEPALIVE
        # plus TCP_KEEPIDLE=45 and friends, the SDK's own values. It stops a
        # connection being dropped as idle *while the process is running*,
        # which is worth having and costs nothing.
        #
        # It does **not** fix the `SSLEOFError: UNEXPECTED_EOF_WHILE_READING`
        # on `/envelope/` it was added for, and the comment that used to stand
        # here saying it did was wrong. Keep-alive probes are sent by the guest
        # kernel, and the platform freezes the entire instance between
        # invocations — kernel included — so nothing is sent during precisely
        # the interval that matters. The cause is one layer up: the send itself
        # is frozen mid-flight. `flush_on_response` is the fix; this stays
        # because it is still correct for the case it does cover.
        keep_alive=True,
        before_send=scrub_event,
    )


def flush_on_response(
    app: Callable[..., Awaitable[None]],
) -> Callable[..., Awaitable[None]]:
    """Wrap an ASGI app so a captured event is delivered before the reply ends.

    The problem is the platform, not the network. Sentry sends on a background
    thread, and Vercel freezes the instance the moment the response is written,
    so an event captured during a request is usually still in flight when the
    freeze lands. It then advances only when the *next* request thaws the
    instance — by which point the socket has long since been dropped at the
    other end. Production showed this exactly: a single retry chain stepping
    2 → 1 → 0 across three invocations fifteen minutes apart, while urllib3's
    backoff between those retries is zero. After the third the event is
    discarded, and `_handle_request_error` re-raises into
    `capture_internal_exceptions()`, so nothing is logged. An app whose crash
    reporter silently drops crashes is worse than one with no reporter.

    Flushing inside the invocation is Sentry's own answer to this environment —
    their AWS Lambda and GCP integrations end every invocation with
    `client.flush()`, commented "flush out the event queue before AWS kills the
    process". There is no Vercel integration, so it is wired up here.

    **This has to wrap the app object itself, and that is not a style choice.**
    The Starlette integration patches `Starlette.__call__` (`patch_asgi_app`),
    which puts `SentryAsgiMiddleware` outside every middleware added with
    `add_middleware` — including where an unhandled exception is finally
    captured. A flush installed the ordinary way would therefore run *before*
    the capture and flush an empty queue. Hence `api/index.py`.

    Only requests that captured something wait: `scrub_event` counts events on
    their way to the transport, and an unchanged counter means there is nothing
    queued. A request that reports nothing — which is nearly all of them — pays
    one integer comparison.

    What this does not cover: an event captured outside a request, at import or
    during startup, still rides the background worker and can still be lost.
    """

    async def flushing_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await app(scope, receive, send)
            return
        before = captures_seen()
        try:
            await app(scope, receive, send)
        finally:
            # `finally`, because the interesting case is the one that raises:
            # the exception has already passed through `SentryAsgiMiddleware`
            # by the time it reaches here, so the event is queued and waiting.
            # Off the event loop for the same reason `/api/health/sentry` does
            # it — `flush` blocks on the worker thread, and blocking here would
            # stall every other request this instance is serving.
            if captures_seen() != before:
                await asyncio.to_thread(sentry_sdk.flush, FLUSH_TIMEOUT)

    return flushing_app
