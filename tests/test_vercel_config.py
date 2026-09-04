"""Deploy-level configuration guards.

vercel.json is the only place production response headers and host handling
are defined — nothing else in the test suite exercises it, so a regression
there (a dropped header block, a reverted redirect) would ship silently.
"""

import base64
import hashlib
import json
import pathlib
import re

CONFIG = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / "vercel.json").read_text(encoding="utf-8")
)


def _headers_for(path: str) -> dict[str, str]:
    """Flatten every header rule that applies to *every* response.

    Host-scoped rules (`has`) are skipped: they fire on one domain only, so
    folding them in here would claim, for instance, that the apex sends the
    noindex meant for the vercel.app host.
    """
    found: dict[str, str] = {}
    for rule in CONFIG.get("headers", []):
        if rule.get("has"):
            continue
        if rule["source"] in ("/(.*)", "/:path*", path):
            found.update({h["key"]: h["value"] for h in rule["headers"]})
    return found


def test_security_headers_applied_to_every_response():
    headers = _headers_for("/")
    # Framing: the app has state-changing screens and persists the Supabase
    # session in the browser, so it must never be embeddable.
    assert headers.get("X-Frame-Options") == "DENY"
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")
    assert headers.get("X-Content-Type-Options") == "nosniff"
    hsts = headers.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts and int(hsts.split("max-age=")[1].split(";")[0]) >= 15552000
    assert headers.get("Referrer-Policy")


def test_cross_origin_isolation_headers():
    """COOP and CORP: the two that `frame-ancestors` does not cover.

    `X-Frame-Options`/`frame-ancestors` stop the app being put *in* someone
    else's frame. Neither says anything about a window that opened this one, or
    about another origin loading our responses directly.

    COOP `same-origin-allow-popups` severs the `window.opener` relationship with
    any cross-origin page that opened the app — an attacker's page can still
    navigate to us, but it cannot keep a handle on the resulting window. The
    `-allow-popups` half is deliberate rather than lazy: the strict value also
    severs popups *we* open, and while supabase-js signs in by full-page
    redirect today, an OAuth popup is one config change away and would break
    silently under `same-origin`. The support link (`target="_blank"`) is the
    other reason.

    CORP `same-origin` stops another site embedding our responses directly —
    the icons, the manifest, the built JS. Nothing legitimately does: every
    asset this app serves is loaded by this app.
    """
    headers = _headers_for("/")
    assert headers.get("Cross-Origin-Opener-Policy") == "same-origin-allow-popups"
    assert headers.get("Cross-Origin-Resource-Policy") == "same-origin"


def _www_redirects() -> list[dict]:
    return [
        r
        for r in CONFIG["redirects"]
        if any(h["type"] == "host" and h["value"] == "www.split-dec.app" for h in r.get("has", []))
    ]


def test_www_still_redirects_to_apex():
    # Installed PWAs pin their origin: the apex must stay the serving origin.
    redirects = _www_redirects()
    assert redirects
    for redirect in redirects:
        assert redirect["destination"].startswith("https://split-dec.app")
        assert redirect["permanent"] is True


def test_www_redirect_covers_the_bare_root():
    """`/:path*` alone does not match `/` on Vercel's router.

    That gap served the SPA shell from www while every other path — including
    `/api/*` — 308'd to the apex, so the app booted on an origin whose API
    calls were a cross-origin hop the CORS-less API refuses. Users typing the
    domain landed there, logged in, and got "Failed to fetch". The explicit
    root rule must stay, and must stay ahead of the catch-all.
    """
    sources = [r["source"] for r in _www_redirects()]
    assert "/" in sources
    if "/:path*" in sources:
        assert sources.index("/") < sources.index("/:path*")


def test_apex_is_indexable():
    """The canonical domain must never carry a noindex — the whole point of
    the host-scoped rule below is that it applies to the *other* host."""
    assert "X-Robots-Tag" not in _headers_for("/")


def test_vercel_domain_is_not_indexable():
    """split-dec.vercel.app serves the same app as the apex, so left alone it
    is duplicate content competing with the canonical domain.

    A host-scoped header is the only way to say so: every route is rewritten
    to a single index.html, so a `<link rel="canonical">` placed in it would
    also claim /privacy and /terms are copies of the landing page.
    """
    rules = [
        r
        for r in CONFIG["headers"]
        if any(
            h["type"] == "host" and h["value"] == "split-dec.vercel.app"
            for h in r.get("has", [])
        )
    ]
    assert rules, "no host-scoped rule for split-dec.vercel.app"
    tags = [h["value"] for r in rules for h in r["headers"] if h["key"] == "X-Robots-Tag"]
    assert tags and all("noindex" in v for v in tags)


# --- The script-level CSP ---------------------------------------------------
#
# The policy was rolled out in two stages: `Content-Security-Policy-Report-Only`
# first, so a directive that turned out to be wrong reported instead of breaking
# the app, then the same string promoted onto the enforcing header. Stage two
# has happened, and these tests now read the enforcing header only — a policy
# that merely reports is a policy that stops nothing, and the whole point of the
# staging was that it would end.

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _parse_csp(policy: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for chunk in policy.split(";"):
        parts = chunk.split()
        if parts:
            directives[parts[0].lower()] = parts[1:]
    return directives


def _full_csp() -> dict[str, list[str]]:
    """The script-level policy, which must be on the *enforcing* header.

    `frame-ancestors 'none'` alone is not it — that is the framing-only policy
    that shipped long before this item.
    """
    headers = _headers_for("/")
    enforced = headers.get("Content-Security-Policy", "")
    assert "script-src" in enforced, (
        "the script-level CSP is not on Content-Security-Policy. A policy that "
        "only reports blocks nothing: injection and exfiltration are governed "
        "by the enforcing header alone."
    )
    assert "script-src" not in headers.get("Content-Security-Policy-Report-Only", ""), (
        "the full policy is on both headers: enforcing and report-only would "
        "drift apart on the next edit — keep exactly one, and keep it enforcing"
    )
    return _parse_csp(enforced)


def _inline_script_hashes() -> set[str]:
    """CSP hashes of every inline script in the served HTML.

    Computed from index.html rather than hard-coded, so editing the theme
    script fails here instead of silently blocking it in production. The regex
    skips `<script src=…>`: external scripts are covered by 'self', and only an
    element's own text is hashed.
    """
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    bodies = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    return {
        "'sha256-" + base64.b64encode(hashlib.sha256(b.encode("utf-8")).digest()).decode() + "'"
        for b in bodies
    }


def test_framing_is_enforced_not_merely_reported():
    """The report-only rollout must not demote the protection already shipped.

    Moving `frame-ancestors` onto the report-only header while the enforcing
    header carried nothing would make the app framable again — a regression
    dressed up as hardening.
    """
    enforced = _headers_for("/").get("Content-Security-Policy", "")
    assert "frame-ancestors 'none'" in enforced


def test_the_whole_policy_is_enforced_and_nothing_is_left_reporting():
    """The staged rollout is over; it must not be reinstated by accident.

    While the full policy sat on `Content-Security-Policy-Report-Only`, every
    directive below — the hash pinning, the closed injection primitives, the
    pinned connect-src origins — described something the browser watched and
    allowed anyway. Moving any of it back to report-only would leave this file
    asserting a policy that is not in force, which is worse than not asserting
    one at all.

    Reporting stays on: `report-uri`/`report-to` work on an enforcing policy
    too, and that is how a directive that turns out to be wrong in the field
    becomes visible rather than just breaking something.
    """
    headers = _headers_for("/")
    assert "Content-Security-Policy-Report-Only" not in headers, (
        "a report-only CSP is back in vercel.json; the enforcing header is the "
        "one that protects anything"
    )
    directives = _full_csp()
    assert directives.get("report-uri"), "the enforcing policy stopped reporting"


def test_csp_pins_the_inline_theme_script_by_hash():
    """index.html runs one inline script (the pre-mount theme flip).

    A nonce is impractical when one static index.html is served through a
    rewrite, so the script is hash-allowed. If it is ever edited, its hash
    changes and this test fails until vercel.json is updated — which is the
    entire point: the alternative is a silent light-mode flash in production.
    """
    script_src = _full_csp()["script-src"]
    expected = _inline_script_hashes()
    assert expected, "index.html no longer has an inline script — drop the hash"
    missing = expected - set(script_src)
    assert not missing, (
        f"index.html's inline script changed; vercel.json must allow {missing}"
    )


def test_csp_does_not_readmit_arbitrary_script():
    """'unsafe-inline'/'unsafe-eval' would make script-src decorative.

    The session lives in localStorage (supabase-js `persistSession`), so an
    injected script means a stealable *refresh* token, not a session that dies
    with the tab. This directive is what stands between the two.
    """
    directives = _full_csp()
    for banned in ("'unsafe-inline'", "'unsafe-eval'", "'strict-dynamic'"):
        assert banned not in directives["script-src"], f"script-src re-admits {banned}"
    # A wide default-src would quietly cover any directive dropped later.
    assert directives["default-src"] == ["'self'"]


def test_csp_closes_the_injection_primitives():
    directives = _full_csp()
    # An injected <base> would repoint every relative script load.
    assert directives["base-uri"] == ["'none'"]
    # Plugins are a script-execution surface the app has no use for.
    assert directives["object-src"] == ["'none'"]
    # Nothing may be framed *into* the app either; it embeds no third party.
    assert directives["frame-src"] == ["'none'"]
    # Stops an injected form posting the DOM (or a password field) off-origin.
    assert directives["form-action"] == ["'self'"]
    assert directives["frame-ancestors"] == ["'none'"]


def test_csp_allows_exactly_the_origins_the_app_uses():
    """Every allowance here is load-bearing; none is speculative."""
    directives = _full_csp()

    # supabase-js talks to the project's auth endpoints from the browser.
    # Pinned to the project, not *.supabase.co — any other project is an
    # attacker-controlled endpoint as far as this app is concerned.
    assert "https://kmlheefyzhhegxmtaovq.supabase.co" in directives["connect-src"]
    # Same-origin covers /api/* and the /_vercel measurement beacons.
    assert "'self'" in directives["connect-src"]

    # Sentry's browser SDK posts envelopes to the org's own ingest subdomain
    # (src/lib/monitoring.ts). Pinned to that host for the same reason Supabase
    # is pinned to the project: `*.ingest.sentry.io` would allow every other
    # tenant on the platform, which is the whole internet as far as this app is
    # concerned. `de.` is load-bearing too — the org is in Sentry's EU region,
    # which is what src/lib/legal.ts tells people.
    assert "https://o4512011830886400.ingest.de.sentry.io" in directives["connect-src"]
    assert not any(
        src.startswith("https://*.") for src in directives["connect-src"]
    ), "connect-src has a wildcard host; pin the exact origin"

    # Google avatars, mirroring src/lib/avatarUrl.ts's allow-list. If a second
    # OAuth provider is ever added, both places need its host.
    assert any("googleusercontent.com" in src for src in directives["img-src"])

    # Vite inlines the smallest Manrope subset as a base64 woff2 in the built
    # CSS, so 'self' alone would drop a font that is actually used.
    assert "data:" in directives["font-src"]

    # worker-src gates /sw.js being *loaded* as a worker, whoever registers it
    # (src/lib/serviceWorker.ts, from the app bundle); manifest-src gates the
    # webmanifest the plugin still injects a <link> for.
    assert "'self'" in directives["worker-src"]
    assert "'self'" in directives["manifest-src"]


def test_the_csp_has_somewhere_to_report_to():
    """A policy with no reporting destination reports to nobody.

    Violations land in each visitor's own console, which no one is watching.
    That mattered while the policy was staged (the condition for promoting it
    could never be met) and it still matters now that it is enforced: a
    directive that is wrong for some flow nobody tested is a feature silently
    broken in the field unless the block reaches a log. Both directives are
    present because no browser honours both: Firefox and Safari have only
    `report-uri`, and Chrome ignores it whenever `report-to` is offered.
    """
    directives = _full_csp()
    assert directives.get("report-uri") == ["/api/csp-report"]
    assert directives.get("report-to") == ["csp-endpoint"]

    # `report-to` names a group; the group is defined by this header, and an
    # undefined group is silently inert.
    endpoints = _headers_for("/").get("Reporting-Endpoints", "")
    assert 'csp-endpoint="' in endpoints
    assert "/api/csp-report" in endpoints
    # Absolute, and on the apex: the Reporting API preflights a cross-origin
    # endpoint and the production API sends no CORS headers, so only a URL that
    # is same-origin *there* is ever delivered. Previews and the vercel.app
    # alias fall back to `report-uri`, which is relative and always same-origin.
    assert 'csp-endpoint="https://split-dec.app/api/csp-report"' in endpoints


def test_reports_go_to_our_own_origin():
    """Sending violations to a third party would be a new processor, and a
    src/lib/legal.ts change with a LEGAL_UPDATED bump — not a header edit."""
    destinations = [
        _full_csp()["report-uri"][0],
        _headers_for("/")["Reporting-Endpoints"].split('"')[1],
    ]
    for destination in destinations:
        assert destination.startswith("/") or destination.startswith("https://split-dec.app/")
