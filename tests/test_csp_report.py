"""The CSP violation collector.

Three things are being tested: that a report survives the trip at all (it is how
a wrong directive in the enforced policy becomes visible instead of silently
breaking a flow), that what reaches the log is narrower than what the browser
sent — no group id, no `?code=`, no `#access_token=`, no page content — and that
the one endpoint a stranger can reach without a token cannot be turned into a
log-flooding primitive.
"""

import logging
import time

import pytest

from _src.routers import reports

GROUP_URL = "https://split-dec.app/groups/2b2f0e1c-9a71-4a51-8d0b-6d1c9b0f7e42"


def _report_uri_body(**overrides) -> dict:
    body = {
        "document-uri": "https://split-dec.app/groups",
        "referrer": "https://split-dec.app/",
        "violated-directive": "script-src-elem",
        "effective-directive": "script-src-elem",
        "original-policy": "default-src 'self'; report-uri /api/csp-report",
        "disposition": "report",
        "blocked-uri": "https://cdn.evil.example/tracker.js?visitor=abc",
        "status-code": 200,
        "script-sample": "eval('secret page content')",
    }
    body.update(overrides)
    return {"csp-report": body}


def _report_to_body(**overrides) -> list:
    body = {
        "documentURL": "https://split-dec.app/groups",
        "referrer": "https://split-dec.app/",
        "blockedURL": "https://cdn.evil.example/tracker.js",
        "effectiveDirective": "script-src-elem",
        "originalPolicy": "default-src 'self'",
        "sourceFile": "https://split-dec.app/assets/index-abc.js",
        "sample": "eval('secret page content')",
        "disposition": "report",
        "statusCode": 200,
    }
    body.update(overrides)
    return [{"type": "csp-violation", "url": body["documentURL"], "age": 0, "body": body}]


@pytest.fixture
def logged(caplog):
    caplog.set_level(logging.WARNING, logger="splitdec.csp")
    return caplog


@pytest.fixture(autouse=True)
def _full_bucket():
    """The token bucket is module state, so it leaks between tests.

    Refilled before each one so a test that deliberately empties it cannot
    silence the next test's reports — and so the order tests happen to run in
    never decides whether they pass.
    """
    reports._tokens = float(reports.REPORTS_PER_MINUTE)
    reports._last_refill = time.monotonic()
    reports._suppressing = False


async def test_report_uri_format_is_accepted_and_logged(client, logged):
    r = await client.post("/api/csp-report", json=_report_uri_body())
    assert r.status_code == 204
    assert "directive=script-src-elem" in logged.text
    assert "route=/groups" in logged.text


async def test_report_to_format_is_accepted_and_logged(client, logged):
    """Chrome ignores `report-uri` when `report-to` is offered, so the array
    envelope is not an alternative shape — it is the one most reports arrive
    in."""
    r = await client.post("/api/csp-report", json=_report_to_body())
    assert r.status_code == 204
    assert "directive=script-src-elem" in logged.text


async def test_blocked_uri_keeps_the_origin_and_drops_the_path(client, logged):
    await client.post("/api/csp-report", json=_report_uri_body())
    assert "blocked=https://cdn.evil.example" in logged.text
    assert "tracker.js" not in logged.text
    assert "visitor=abc" not in logged.text


async def test_csp_keywords_survive_intact(client, logged):
    """'inline' and 'eval' are not URLs, and they are the two that matter most
    while a script-src policy is being validated."""
    await client.post("/api/csp-report", json=_report_uri_body(**{"blocked-uri": "inline"}))
    assert "blocked=inline" in logged.text


async def test_group_identifiers_are_folded_out_of_the_route(client, logged):
    await client.post("/api/csp-report", json=_report_uri_body(**{"document-uri": GROUP_URL}))
    assert "route=/groups/[groupId]" in logged.text
    assert "2b2f0e1c" not in logged.text


async def test_credentials_in_the_document_url_never_reach_the_log(client, logged):
    """The OAuth callback carries `?code=` and a recovery link
    `#access_token=`. A violation reported on either would otherwise put a live
    credential in a log line."""
    await client.post(
        "/api/csp-report",
        json=_report_uri_body(
            **{"document-uri": "https://split-dec.app/login?code=live-oauth-code"}
        ),
    )
    await client.post(
        "/api/csp-report",
        json=_report_uri_body(
            **{"document-uri": "https://split-dec.app/reset-password#access_token=live-jwt"}
        ),
    )
    assert "live-oauth-code" not in logged.text
    assert "live-jwt" not in logged.text
    assert "route=/login" in logged.text
    assert "route=/reset-password" in logged.text


async def test_page_content_and_referrer_are_never_logged(client, logged):
    for payload in (_report_uri_body(), _report_to_body()):
        await client.post("/api/csp-report", json=payload)
    assert "secret page content" not in logged.text
    assert "referrer" not in logged.text.lower()
    # sourceFile is a URL like any other and stays out too.
    assert "index-abc.js" not in logged.text


async def test_oversized_body_is_refused_without_logging(client, logged):
    """The endpoint is the one route on the API a stranger can reach without a
    token, so it must not be a log-flooding primitive."""
    padded = _report_uri_body(**{"original-policy": "x" * reports.MAX_REPORT_BYTES})
    r = await client.post("/api/csp-report", json=padded)
    assert r.status_code == 413
    assert logged.text == ""


async def test_malformed_body_is_refused(client, logged):
    r = await client.post(
        "/api/csp-report",
        content=b"{not json",
        headers={"Content-Type": "application/csp-report"},
    )
    assert r.status_code == 400
    assert logged.text == ""


async def test_unrecognized_but_valid_json_is_accepted_quietly(client, logged):
    """The browser never reads this response, so a well-formed body carrying
    no violation is not worth an error status."""
    for payload in ({}, [], {"csp-report": "not an object"}, [{"type": "deprecation"}]):
        r = await client.post("/api/csp-report", json=payload)
        assert r.status_code == 204
    assert logged.text == ""


async def test_no_authentication_is_required(client):
    """Browsers post these with no credentials; requiring a token would mean
    collecting nothing."""
    from _src.auth import verify_jwt
    from _src.main import app

    # The suite's client overrides verify_jwt globally; drop it for this one
    # call so the route is exercised with the real dependency in place.
    override = app.dependency_overrides.pop(verify_jwt)
    try:
        r = await client.post("/api/csp-report", json=_report_uri_body())
        assert r.status_code == 204
    finally:
        app.dependency_overrides[verify_jwt] = override


async def test_no_field_can_forge_a_second_log_line(client, logged):
    """Every field logged here comes out of a body anyone can post. A newline
    in one of them would write a log line of the attacker's choosing."""
    await client.post(
        "/api/csp-report",
        json=_report_uri_body(
            **{
                "effective-directive": "img-src\ncsp violation: directive=all-clear",
                "violated-directive": "img-src\nforged",
                "disposition": "report\nforged",
                "blocked-uri": "inline\nforged",
            }
        ),
    )
    assert "forged" not in logged.text
    assert "all-clear" not in logged.text
    assert len(logged.records) == 1


def test_fold_route_mirrors_the_frontend():
    """`insightsRoute` in src/App.tsx does the same fold for the measurement
    products. A new dynamic route has to be added in both places."""
    assert reports.fold_route(GROUP_URL) == "/groups/[groupId]"
    assert reports.fold_route(f"{GROUP_URL}/expenses") == "/groups/[groupId]/expenses"
    assert reports.fold_route("https://split-dec.app/") == "/"
    assert reports.fold_route("") == "-"
    assert reports.fold_route("inline") == "-"  # not a document URL


def test_normalize_handles_a_partial_report():
    """Browsers disagree about which fields they send; a missing one must not
    cost the whole report — except `document-uri`, whose absence leaves nothing
    to attribute the report to. `origin: None` is how the endpoint is told to
    drop it."""
    [report] = reports.normalize({"csp-report": {"violated-directive": "img-src"}})
    assert report == {
        "directive": "img-src",
        "blocked": "-",
        "route": "-",
        "origin": None,
        "disposition": "report",
    }


# --- What an unauthenticated stranger can make this do ----------------------


async def test_a_body_that_does_not_claim_to_be_a_report_is_refused(client, logged):
    """Rejected on the header, before the body is read.

    Browsers send `application/csp-report` or `application/reports+json`;
    anything else was never a violation report, and answering it without
    touching the payload is the cheapest thing this route can do.
    """
    r = await client.post(
        "/api/csp-report",
        content=b'{"csp-report": {}}',
        headers={"Content-Type": "text/plain"},
    )
    assert r.status_code == 415
    assert logged.text == ""


@pytest.mark.parametrize(
    "content_type",
    ["application/csp-report", "application/reports+json", "application/json"],
    ids=["report-uri", "report-to", "curl"],
)
async def test_the_content_types_browsers_actually_send_are_accepted(
    client, logged, content_type
):
    import json as _json

    r = await client.post(
        "/api/csp-report",
        content=_json.dumps(_report_uri_body()).encode(),
        headers={"Content-Type": f"{content_type}; charset=utf-8"},
    )
    assert r.status_code == 204
    assert "csp violation" in logged.text


async def test_a_report_from_a_document_we_do_not_serve_is_dropped(client, logged):
    """Anyone can point their own site's `report-uri` at this endpoint, or post
    by hand. A page we never served was never handed our policy, so its
    violations say nothing about ours — and every one of them would be a log
    line of a stranger's choosing."""
    for foreign in (
        "https://attacker.example/anything",
        "https://split-dec.app.attacker.example/",  # host merely starts right
        "https://notsplit-dec.vercel.app/",
        "http://split-dec.app/",  # https only
    ):
        r = await client.post("/api/csp-report", json=_report_uri_body(**{"document-uri": foreign}))
        assert r.status_code == 204, foreign
    assert logged.text == ""


async def test_preview_deployments_are_still_collected(client, logged):
    """Previewing is where a policy change gets exercised before it ships, so
    the project's own vercel.app hosts have to keep reporting."""
    for host in ("split-dec.vercel.app", "split-dec-abc123-t5chrono.vercel.app"):
        await client.post(
            "/api/csp-report", json=_report_uri_body(**{"document-uri": f"https://{host}/groups"})
        )
        assert f"origin={host}" in logged.text


async def test_the_reporting_host_is_logged(client, logged):
    await client.post("/api/csp-report", json=_report_uri_body())
    assert "origin=split-dec.app" in logged.text


async def test_a_batch_cannot_multiply_into_unbounded_log_lines(client, logged):
    """The body cap alone does not cap log lines: one `report-to` POST is an
    array, and 16 kB of minimal envelopes is a few hundred entries."""
    [envelope] = _report_to_body()
    batch = [envelope] * (reports.MAX_REPORTS_PER_REQUEST + 25)
    r = await client.post("/api/csp-report", json=batch)
    assert r.status_code == 204
    assert len(logged.records) == reports.MAX_REPORTS_PER_REQUEST


async def test_the_token_bucket_clips_a_flood_and_says_so_once(client, logged, monkeypatch):
    """Per warm instance, not global — the real ceiling is an edge rate limit
    (see the module docstring). What this asserts is that the floor exists and
    that the notice about it does not itself become the flood."""
    monkeypatch.setattr(reports, "REPORTS_PER_MINUTE", 2)
    reports._tokens = 2.0
    reports._last_refill = time.monotonic()

    for _ in range(6):
        r = await client.post("/api/csp-report", json=_report_uri_body())
        assert r.status_code == 204  # the sender is never told it was clipped

    violations = [m for m in logged.messages if m.startswith("csp violation:")]
    suppressed = [m for m in logged.messages if "suppressed" in m]
    assert len(violations) == 2
    assert len(suppressed) == 1, "the suppression notice must not repeat per drop"
