"""Collector for Content-Security-Policy violation reports.

The full script-level policy ships as `Content-Security-Policy-Report-Only`
(vercel.json), to be promoted onto the enforcing header once the reports come
back clean. That plan had a missing prerequisite: a report-only policy with no
reporting destination sends its violations to each visitor's own console, where
nobody collects them — so "clean" could never be established and the policy
would have stayed staged indefinitely.

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
directive fired, the *origin* the blocked thing came from, and the route
pattern it happened on, folded exactly as `insightsRoute` folds it for the
measurement products (src/App.tsx). So this adds no category of data beyond
what `src/lib/legal.ts` already discloses about server logs. Sending reports to
a third-party collector instead would: that is a new processor, and a legal.ts
change with a `LEGAL_UPDATED` bump.
"""

import json
import logging
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["reports"])

logger = logging.getLogger("splitdec.csp")

# Larger than any honest report — the biggest field is the policy string echoed
# back — and small enough that an unauthenticated stranger cannot use the
# endpoint to flood the log one request at a time.
MAX_REPORT_BYTES = 16 * 1024

_DYNAMIC_SEGMENTS = ((re.compile(r"^/groups/[^/]+"), "/groups/[groupId]"),)

# The shape of a CSP keyword: the values `blocked-uri` can carry instead of a
# URL ('inline', 'eval', 'data', 'trusted-types-policy', …), every directive
# name, and the two dispositions. Every one of those fields comes out of an
# attacker-controlled body, and one containing a newline would forge a second
# line in the log — so anything that is not this shape is dropped rather than
# logged.
_KEYWORD = re.compile(r"[a-z-]{1,32}")


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


def normalize(payload: object) -> list[dict[str, str]]:
    """Both wire formats, reduced to the fields worth keeping.

    No browser sends both: `report-uri` posts one `{"csp-report": {...}}`
    object with kebab-case keys (Firefox, Safari), while `report-to` posts a
    JSON array of Reporting API envelopes whose `body` is camelCase (Chrome,
    which ignores `report-uri` when both are offered). The policy carries both
    directives, so this accepts both shapes.
    """
    if isinstance(payload, dict) and isinstance(payload.get("csp-report"), dict):
        report = payload["csp-report"]
        return [
            {
                "directive": keyword(
                    report.get("effective-directive") or report.get("violated-directive") or ""
                ),
                "blocked": fold_blocked(report.get("blocked-uri") or ""),
                "route": fold_route(report.get("document-uri") or ""),
                "disposition": keyword(report.get("disposition") or "report"),
            }
        ]
    if isinstance(payload, list):
        collected = []
        for envelope in payload:
            if not isinstance(envelope, dict) or envelope.get("type") != "csp-violation":
                continue
            body = envelope.get("body")
            if not isinstance(body, dict):
                continue
            collected.append(
                {
                    "directive": keyword(body.get("effectiveDirective") or ""),
                    "blocked": fold_blocked(body.get("blockedURL") or ""),
                    "route": fold_route(body.get("documentURL") or envelope.get("url") or ""),
                    "disposition": keyword(body.get("disposition") or "report"),
                }
            )
        return collected
    return []


@router.post("/csp-report", status_code=204)
async def csp_report(request: Request) -> Response:
    """Record a CSP violation. Always cheap, never authenticated, never stored.

    The browser discards whatever this answers, so the status codes are for
    whoever is holding curl: 413 for a body over the cap, 400 for something
    that is not JSON, 204 for anything understood — including a well-formed
    body carrying no violation, which is not an error worth reporting to a
    sender that cannot read it.
    """
    body = await request.body()
    if len(body) > MAX_REPORT_BYTES:
        return Response(status_code=413)
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return Response(status_code=400)
    for report in normalize(payload):
        # WARNING, not INFO: the root logger's default level is WARNING and
        # nothing here configures it, so anything quieter would be dropped
        # before it reached the function log this endpoint exists to fill.
        logger.warning(
            "csp violation: directive=%s blocked=%s route=%s disposition=%s",
            report["directive"],
            report["blocked"],
            report["route"],
            report["disposition"],
        )
    return Response(status_code=204)
