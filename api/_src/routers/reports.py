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

**Three things bound what an unauthenticated stranger can make this do**, in
increasing order of how much they are worth: a body cap, a per-request report
cap, and a per-process token bucket. None of them is a global rate limit and
none of them can be — this is a serverless function with several instances and
constant cold starts, so a caller spraying requests is spread across buckets
that cannot see each other, and the effective ceiling is the bucket rate times
however many instances the platform decided to run. **The global limit belongs
at the edge** (a Vercel Firewall rate-limit rule on `/api/csp-report`), where
one counter sees every request; what is here is the cheap floor that keeps a
single caller from filling the log through one warm instance, and it should
never be mistaken for the ceiling.
"""

import json
import logging
import re
import time
from urllib.parse import urlsplit

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
# attacker-controlled body, and one containing a newline would forge a second
# line in the log — so anything that is not this shape is dropped rather than
# logged.
_KEYWORD = re.compile(r"[a-z-]{1,32}")

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


def fold_blocked(value: str) -> str:
    """Where the blocked thing came from, without the path it came from.

    `blocked-uri` is either one of CSP's own keywords ('inline', 'eval',
    'data') or a URL. The origin is what says whether the policy is wrong; the
    rest is a path on somebody else's host — or on ours, where a blocked
    `connect-src` fetch would spell out a group id.
    """
    if not value:
        return "-"
    if "://" not in value:
        # Matched by shape rather than against a list, so a keyword the spec
        # grows later still comes through.
        return keyword(value)
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}" if parts.netloc else "-"


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
    logger.warning(
        "csp violation: directive=%s blocked=%s route=%s origin=%s disposition=%s",
        report["directive"],
        report["blocked"],
        report["route"],
        report["origin"],
        report["disposition"],
    )


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
        return Response(status_code=415)
    body = await request.body()
    if len(body) > MAX_REPORT_BYTES:
        return Response(status_code=413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=400)
    for report in normalize(payload)[:MAX_REPORTS_PER_REQUEST]:
        if report["origin"] is None:
            continue
        _record(report)
    return Response(status_code=204)
