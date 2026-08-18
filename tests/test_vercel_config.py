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


# --- The script-level CSP (GO-LIVE 12.1) ------------------------------------
#
# The policy is rolled out in two stages: `Content-Security-Policy-Report-Only`
# first, so a directive that turns out to be wrong reports instead of breaking
# the app, then the same string promoted onto the enforcing header. These tests
# read whichever header carries the full policy, so promoting it is a one-word
# change in vercel.json and not a test rewrite.

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _parse_csp(policy: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    for chunk in policy.split(";"):
        parts = chunk.split()
        if parts:
            directives[parts[0].lower()] = parts[1:]
    return directives


def _full_csp() -> dict[str, list[str]]:
    """The script-level policy, whichever header is currently carrying it.

    `frame-ancestors 'none'` alone is not it — that is the framing-only policy
    that shipped long before this item.
    """
    headers = _headers_for("/")
    carriers = [
        value
        for key in ("Content-Security-Policy", "Content-Security-Policy-Report-Only")
        if "script-src" in (value := headers.get(key, ""))
    ]
    assert carriers, "no script-level CSP is served on any header"
    assert len(carriers) == 1, (
        "the full policy is on both headers: enforcing and report-only would "
        "drift apart on the next edit — keep exactly one"
    )
    return _parse_csp(carriers[0])


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

    # Google avatars, mirroring src/lib/avatarUrl.ts's allow-list. If a second
    # OAuth provider is ever added, both places need its host.
    assert any("googleusercontent.com" in src for src in directives["img-src"])

    # Vite inlines the smallest Manrope subset as a base64 woff2 in the built
    # CSS, so 'self' alone would drop a font that is actually used.
    assert "data:" in directives["font-src"]

    # The PWA service worker registers from /registerSW.js.
    assert "'self'" in directives["worker-src"]
    assert "'self'" in directives["manifest-src"]
