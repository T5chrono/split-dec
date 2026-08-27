"""The CSP violation collector.

Two things are being tested: that a report survives the trip at all (it is the
prerequisite for ever promoting the staged policy), and that what reaches the
log is narrower than what the browser sent — no group id, no `?code=`, no
`#access_token=`, no page content.
"""

import logging

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
    cost the whole report."""
    [report] = reports.normalize({"csp-report": {"violated-directive": "img-src"}})
    assert report == {
        "directive": "img-src",
        "blocked": "-",
        "route": "-",
        "disposition": "report",
    }
