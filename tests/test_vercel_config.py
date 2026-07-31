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
    """Flatten every header rule whose source matches everything."""
    found: dict[str, str] = {}
    for rule in CONFIG.get("headers", []):
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
