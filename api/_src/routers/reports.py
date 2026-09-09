"""Collector for Content-Security-Policy violation reports.

The script-level policy is enforced (vercel.json) and still reports, so this
endpoint outlives the rollout it was built for: it is how a directive that
turns out to be wrong in the field becomes visible instead of just breaking
something quietly in one visitor's browser.

Deliberately not a database write. Browsers post these unauthenticated, so this
is the one endpoint on the API a stranger can reach without a token: a row per
report would hand them an open write primitive, and taking a pooler connection
per report would be worse. Reports go to the function's log, which Vercel
already collects, and nothing is retained beyond it.

What gets logged is narrower than what browsers send, on purpose. A report
carries `document-uri`, `referrer`, `source-file` and a `script-sample`; the
first three are full URLs, which on this app can carry a group id — and, on the
OAuth callback and the recovery link, a live `?code=` or `#access_token=`. The
sample is page content. Only the shape of the violation is kept: which
directive fired, the *origin* the blocked thing came from, the host that
reported it, and the route pattern it happened on, folded exactly as
`insightsRoute` folds it for the measurement products (src/App.tsx). So this
adds no category of data beyond what `src/lib/legal.ts` already discloses about
server logs. Sending reports to a third-party collector instead would: that is
a new processor, and a legal.ts change with a `LEGAL_UPDATED` bump.

**Every field is percent-encoded on the way into the log line** (`log_value`).
The line is five `name=value` pairs separated by spaces and all five values come
out of a body anyone can post, so stripping CR/LF was never enough: a route of
`/a route=x origin=evil` forges two more fields on the same physical line, and a
`blocked-uri` authority can do the same. Encoding at the output boundary is the
same move as binding a SQL parameter — the value can no longer be read as part
of the format around it. A consumer therefore splits on the field boundaries
first and decodes values afterwards.

**Three things bound what an unauthenticated stranger can make this do**, in
increasing order of how much they are worth: a body cap, a per-request report
cap, and a per-process token bucket. None of them is a global rate limit and
none of them can be — this is a serverless function with several instances and
constant cold starts, so a caller spraying requests is spread across buckets
that cannot see each other, and the effective ceiling is the bucket rate times
however many instances the platform decided to run. What is here is the cheap
floor that keeps a single caller from filling the log through one warm
instance, and it must never be mistaken for the ceiling.

**The ceiling is at the edge**, where one counter sees every request: a Vercel
Firewall rule named "CSP report flood limit", `path equals /api/csp-report`,
100 requests per 60s keyed by IP, denying for 5m once tripped. That rule lives
in the Vercel project, not in this repo, so it is invisible from here and from
CI — if the numbers below change, change it too (`vercel firewall rules list`),
the same "the dashboard is what actually runs" trap the auth email templates
carry. Denying is safe: browsers discard whatever this endpoint answers, so a
throttled reporter loses telemetry and nothing else.
"""

import json
import logging
import re
import string
import time
from urllib.parse import SplitResult, urlsplit

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["reports"])

logger = logging.getLogger("splitdec.csp")

# Larger than any honest report — the biggest field is the policy string echoed
# back — and small enough that an unauthenticated stranger cannot use the
# endpoint to flood the log one request at a time.
MAX_REPORT_BYTES = 16 * 1024

# One `report-to` POST is an *array*, so the body cap alone does not cap log
# lines: 16 kB of minimal envelopes is a few hundred of them. A real batch is a
# handful.
MAX_REPORTS_PER_REQUEST = 10

# Per warm instance, not per deployment — see the module docstring. Sized so a
# genuine incident (a bad deploy violating one directive on every page load)
# still comes through for a good while before it starts being clipped.
REPORTS_PER_MINUTE = 60

# What browsers actually send: `application/csp-report` for a `report-uri` POST
# and `application/reports+json` for `report-to`. `application/json` is here for
# curl and for the tests. Anything else is not a report, and refusing it on the
# header costs nothing — the body is never read.
ALLOWED_CONTENT_TYPES = frozenset(
    {"application/csp-report", "application/reports+json", "application/json"}
)

_DYNAMIC_SEGMENTS = ((re.compile(r"^/groups/[^/]+"), "/groups/[groupId]"),)

# The hosts this app is served from, and therefore the only ones that can have
# been handed the policy that produced a report. Anything else is either
# somebody pointing their own site's `report-uri` at us or somebody posting by
# hand; neither tells us anything about our policy, and both are log noise.
#
# Preview deployments are in, because previewing is where a policy change gets
# exercised before it ships. `localhost` is out: `npm run dev` never sees
# vercel.json's headers, so no report legitimately originates there.
#
# The trailing team slug is the load-bearing part of the preview pattern.
# Vercel preview hosts are `<project>-<hash>-<team>.vercel.app` (and
# `<project>-git-<branch>-<team>...` for branch aliases), and **project names
# are not globally reserved** — a bare `^split-dec[a-z0-9-]*\.vercel\.app$`
# would also accept a stranger's project named `split-dec-anything`. Account
# slugs *are* globally unique, so pinning to ours is what actually scopes this
# to our own deployments. Cost of the tighter rule: renaming the Vercel team
# silently stops preview reports, and this line is where to fix that.
_ALLOWED_HOSTS = frozenset(
    {"split-dec.app", "www.split-dec.app", "split-dec.vercel.app"}
)
_ALLOWED_HOST_PATTERN = re.compile(
    r"^split-dec-[a-z0-9-]+-t5chronos-projects\.vercel\.app$"
)

# The shape of a CSP keyword: the values `blocked-uri` can carry instead of a
# URL ('inline', 'eval', 'data', 'trusted-types-policy', …), every directive
# name, and the two dispositions. Every one of those fields comes out of an
# attacker-controlled body, so anything that is not this shape is dropped rather
# than logged — narrower than `log_value` would leave it, and the narrower
# answer is the more useful one for a field whose whole vocabulary is known.
_KEYWORD = re.compile(r"[a-z-]{1,32}")

# The alphabet a logged field may use verbatim. Everything else — spaces, `=`,
# `%`, control characters, and every non-ASCII byte — is percent-encoded on the
# way out (`log_value`).
#
# It is an allow-list rather than a list of characters to strip because the
# fields below are folded, not validated: `fold_route` returns whatever path the
# reporter put in the document URL, and a host can be anything `urlsplit` was
# willing to call one. Stripping CR/LF was never enough — the log line is five
# `name=value` pairs separated by spaces, so `route=/a route=x origin=evil`
# forges two fields without a newline anywhere in it.
#
# `/ : . _ ~ - [ ]` are in because they are what a route and an authority are
# made of, brackets included (an IPv6 host is logged bracketed). The cost of
# encoding `%` is that a path which was already percent-encoded reads
# double-encoded in the log; that is the price of the log being unambiguous, and
# a consumer splits on the field boundaries before decoding a value.
_LOG_SAFE = frozenset(string.ascii_letters + string.digits + "/:._~-[]")

# An encoded field longer than this is dropped rather than truncated. Nothing
# honest comes close — the longest real field is a route — and a truncated value
# is a value somebody may still try to read as a whole one.
MAX_LOG_FIELD = 512


def log_value(value: str | None) -> str:
    """One field of a log line, as a single unambiguous token.

    Percent-encoding at the output boundary is what separates a value from the
    delimiters of the format it is going into, the same way quoting separates a
    string from the SQL around it. Doing it here rather than inside each folding
    helper means a new field cannot be added to the log line without it.
    """
    if not value:
        return "-"
    encoded = "".join(
        chr(byte) if chr(byte) in _LOG_SAFE else f"%{byte:02X}"
        for byte in value.encode("utf-8", "surrogatepass")
    )
    return encoded if len(encoded) <= MAX_LOG_FIELD else "-"


# Token bucket state. Module-level and mutated without a lock because the
# helper below has no `await` in it: within one event loop it runs to
# completion, so there is no interleaving to protect against.
_tokens = float(REPORTS_PER_MINUTE)
_last_refill = time.monotonic()
_suppressing = False


def keyword(value: str) -> str:
    return value if _KEYWORD.fullmatch(value or "") else "-"


def fold_route(url: str) -> str:
    """A URL reduced to its route pattern.

    Mirrors `insightsRoute` in src/App.tsx — a new dynamic route has to be
    added in both places, for the same two reasons: one bucket per group tells
    you nothing, and group identifiers do not belong in measurement.

    Query and fragment are dropped outright rather than folded. A violation
    reported on the OAuth callback would otherwise log `?code=`, and one on a
    recovery link `#access_token=` — a live credential in a log line.
    """
    if not url:
        return "-"
    try:
        path = urlsplit(url).path or "/"
    except ValueError:
        return "-"
    if not path.startswith("/"):
        # Not a document URL at all. The body is attacker-controlled, and a
        # value that reaches the log unrecognized is one that could forge a
        # second log line.
        return "-"
    for pattern, replacement in _DYNAMIC_SEGMENTS:
        path = pattern.sub(replacement, path)
    return path


def fold_origin(url: str) -> str | None:
    """The reporting host, if it is one of ours; otherwise `None`.

    `None` means "drop this report". A document URL we do not serve cannot be
    a page that was given our policy, and a report with no document URL at all
    cannot be attributed to one either — every browser sends the field, so an
    absent one says more about the sender than about the app.

    Only the host is kept, never the port or the path: the value that comes
    back is one of a fixed set of strings, which is also what makes it safe to
    put in a log line without the newline check the free-text fields need.
    """
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme != "https":
        return None
    host = parts.hostname or ""
    if host in _ALLOWED_HOSTS or _ALLOWED_HOST_PATTERN.fullmatch(host):
        return host
    return None


def authority(parts: SplitResult) -> str | None:
    """`host` or `host:port`, rebuilt rather than copied out of `netloc`.

    `netloc` is the raw authority text, which carries two things that must not
    reach a log: `user:password@` credentials, and whatever else `urlsplit` was
    willing to leave in it — it validates nothing, so
    `https://blocked.example disposition=enforce` parses with all of that as the
    host. Going through `.hostname` and `.port` drops the userinfo and makes the
    port a number or an error.

    `.hostname` strips the brackets from an IPv6 literal, so they are put back:
    without them `[::1]:443` and a host called `::1:443` are the same string.
    """
    try:
        host = parts.hostname
        port = parts.port  # raises on a malformed port, e.g. `host:notaport`
    except ValueError:
        return None
    if not host:
        return None
    if ":" in host:
        host = f"[{host}]"
    return f"{host}:{port}" if port is not None else host


def fold_blocked(value: str) -> str:
    """Where the blocked thing came from, without the path it came from.

    `blocked-uri` is either one of CSP's own keywords ('inline', 'eval',
    'data') or a URL. The origin is what says whether the policy is wrong; the
    rest is a path on somebody else's host — or on ours, where a blocked
    `connect-src` fetch would spell out a group id.

    The scheme is kept as `urlsplit` parsed it rather than checked against a
    list: `ws:`, `blob:` and `chrome-extension:` all show up in real reports,
    and a scheme the spec grows later is telemetry we would otherwise throw
    away. `urlsplit` only recognizes one at all if it matches CSP's own
    letters-digits-`+.-` shape.
    """
    if not value:
        return "-"
    if "://" not in value:
        # Matched by shape rather than against a list, so a keyword the spec
        # grows later still comes through.
        return keyword(value)
    try:
        parts = urlsplit(value)
    except ValueError:
        return "-"
    host = authority(parts)
    if not parts.scheme or host is None:
        return "-"
    return f"{parts.scheme}://{host}"


def normalize(payload: object) -> list[dict[str, str | None]]:
    """Both wire formats, reduced to the fields worth keeping.

    No browser sends both: `report-uri` posts one `{"csp-report": {...}}`
    object with kebab-case keys (Firefox, Safari), while `report-to` posts a
    JSON array of Reporting API envelopes whose `body` is camelCase (Chrome,
    which ignores `report-uri` when both are offered). The policy carries both
    directives, so this accepts both shapes.

    `origin` is `None` for a report that did not come from a host we serve;
    the endpoint drops those. It is carried here rather than checked earlier
    because the document URL is folded away by the time the caller sees it.
    """
    if isinstance(payload, dict) and isinstance(payload.get("csp-report"), dict):
        report = payload["csp-report"]
        document = report.get("document-uri") or ""
        return [
            {
                "directive": keyword(
                    report.get("effective-directive") or report.get("violated-directive") or ""
                ),
                "blocked": fold_blocked(report.get("blocked-uri") or ""),
                "route": fold_route(document),
                "origin": fold_origin(document),
                "disposition": keyword(report.get("disposition") or "report"),
            }
        ]
    if isinstance(payload, list):
        collected: list[dict[str, str | None]] = []
        for envelope in payload:
            if not isinstance(envelope, dict) or envelope.get("type") != "csp-violation":
                continue
            body = envelope.get("body")
            if not isinstance(body, dict):
                continue
            document = body.get("documentURL") or envelope.get("url") or ""
            if not isinstance(document, str):
                continue
            collected.append(
                {
                    "directive": keyword(body.get("effectiveDirective") or ""),
                    "blocked": fold_blocked(body.get("blockedURL") or ""),
                    "route": fold_route(document),
                    "origin": fold_origin(document),
                    "disposition": keyword(body.get("disposition") or "report"),
                }
            )
        return collected
    return []


def _take_token() -> bool:
    """One log line's worth of budget, or `False` if the bucket is empty."""
    global _tokens, _last_refill
    now = time.monotonic()
    _tokens = min(
        float(REPORTS_PER_MINUTE),
        _tokens + (now - _last_refill) * (REPORTS_PER_MINUTE / 60.0),
    )
    _last_refill = now
    if _tokens < 1.0:
        return False
    _tokens -= 1.0
    return True


def _record(report: dict[str, str | None]) -> None:
    """Log one violation, unless the bucket says we are already shouting.

    The suppression notice is emitted once per drought rather than once per
    dropped report — otherwise the thing announcing the flood becomes the
    flood. It costs no token, which is safe because it can only alternate with
    a successful line.
    """
    global _suppressing
    if not _take_token():
        if not _suppressing:
            _suppressing = True
            logger.warning("csp violation reports suppressed: rate limit reached")
        return
    _suppressing = False
    # WARNING, not INFO: the root logger's default level is WARNING and
    # nothing here configures it, so anything quieter would be dropped
    # before it reached the function log this endpoint exists to fill.
    # Every value goes through `log_value`, including the two that are already
    # constrained to a keyword and the one that comes from a fixed set of hosts.
    # Uniformly, so that the encoding is a property of the log line rather than
    # something each field is individually trusted to have done.
    logger.warning(
        "csp violation: directive=%s blocked=%s route=%s origin=%s disposition=%s",
        log_value(report["directive"]),
        log_value(report["blocked"]),
        log_value(report["route"]),
        log_value(report["origin"]),
        log_value(report["disposition"]),
    )


# The answer to a CORS preflight, and the reason it is a wildcard.
#
# A `report-to` delivery is preflighted even though the endpoint is
# same-origin, because the browser's reporting service sends it from outside
# the document rather than from the page, and
# `Content-Type: application/reports+json` is not CORS-safelisted. Until this
# existed the route answered `OPTIONS` with 405 and no
# `Access-Control-Allow-*` at all, so every preflight failed, the POST that
# would have followed was never sent, and the endpoint had received nothing
# since the day it was written. Chrome then retried the same undelivered
# report on a lengthening backoff, which is what the periodic `OPTIONS ... 405`
# in the production log was.
#
# That is the whole reason both channels are configured and only one is used:
# a policy carrying `report-to` makes Chromium ignore `report-uri` entirely,
# so the working legacy path was switched off by the presence of the broken
# modern one.
#
# `*` rather than an echo of `Origin`, deliberately, and it gives nothing
# away. CORS governs what a *browser* will let a page read back, and this
# route answers 204 with an empty body to everyone; it is unauthenticated by
# necessity, so there is no session for a wildcard to expose. It never sees
# credentials — reports are sent with `credentials: "omit"`, and
# `Allow-Credentials` is deliberately absent, which is also what makes `*`
# legal here. And CORS was never the control on *whose* reports get recorded:
# `fold_origin` drops anything whose `document-uri` is not a host we serve,
# on the body, where a caller holding curl is bound by it too and CORS would
# not reach. Narrowing this to an allow-list would restrict only the browsers
# already covered by that check, while adding a second place for report
# delivery to break silently — which is exactly what happened here.
#
# `Max-Age` so a reporter that is delivering steadily is not preflighting
# every time. The `no-store` middleware (main.py) also stamps these responses;
# it does not reach the preflight cache, which is specified separately.
_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
}


def _answer(status: int) -> Response:
    """Every response this route gives, CORS headers included.

    On the actual POST as much as on the preflight: a report delivery whose
    response carries no `Access-Control-Allow-Origin` is a failed fetch as far
    as the browser is concerned, so the report goes back on the retry queue
    even though the function has already logged it.
    """
    return Response(status_code=status, headers=_CORS_HEADERS)


def content_type_allowed(header: str | None) -> bool:
    """`application/csp-report; charset=utf-8` and friends, parameters aside."""
    if not header:
        return False
    return header.split(";")[0].strip().lower() in ALLOWED_CONTENT_TYPES


@router.post("/csp-report", status_code=204)
async def csp_report(request: Request) -> Response:
    """Record a CSP violation. Always cheap, never authenticated, never stored.

    The browser discards whatever this answers, so the status codes are for
    whoever is holding curl: 415 for a body that does not claim to be a report,
    413 for one over the cap, 400 for something that is not JSON, 204 for
    anything understood — including a well-formed body carrying no violation,
    or one from a host we do not serve, neither of which is an error worth
    reporting to a sender that cannot read it.
    """
    if not content_type_allowed(request.headers.get("content-type")):
        # Refused before the body is read, which is the point: this is the
        # cheapest possible answer to a request that was never a report.
        return _answer(415)
    body = await request.body()
    if len(body) > MAX_REPORT_BYTES:
        return _answer(413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return _answer(400)
    for report in normalize(payload)[:MAX_REPORTS_PER_REQUEST]:
        if report["origin"] is None:
            continue
        _record(report)
    return _answer(204)


@router.options("/csp-report", status_code=204)
async def csp_report_preflight() -> Response:
    """Let the browser's reporting service through to the POST above.

    Takes no arguments and inspects nothing: the preflight carries no body and
    the answer does not vary by caller (see `_CORS_HEADERS`). It is a fixed
    204 with four headers, which is also the cheapest thing this function can
    do on a route a stranger can reach.
    """
    return _answer(204)
