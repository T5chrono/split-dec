"""Deploy-level configuration guards.

vercel.json is the only place production response headers and host handling
are defined — nothing else in the test suite exercises it, so a regression
there (a dropped header block, a reverted redirect) would ship silently.
"""

import json
import pathlib

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
