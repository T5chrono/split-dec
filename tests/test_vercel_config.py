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


def test_www_still_redirects_to_apex():
    # Installed PWAs pin their origin: the apex must stay the serving origin.
    redirect = CONFIG["redirects"][0]
    assert redirect["has"][0]["value"] == "www.split-dec.app"
    assert redirect["destination"].startswith("https://split-dec.app")
    assert redirect["permanent"] is True
