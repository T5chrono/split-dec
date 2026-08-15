"""The interactive API docs must not exist in production.

FastAPI's Swagger page pulls `swagger-ui-bundle.js` from cdn.jsdelivr.net at an
unpinned major version with no SRI, so serving it from `/api/docs` puts a
third-party script on the very origin that holds the user's Supabase session.
`/api/openapi.json` is the other half: it is what that page fetches, and alone
it enumerates every endpoint and schema.

**Why most of this tests `docs_urls` rather than probing `app` for a missing
route.** `app` is constructed at *import* time from whatever ENV the
developer's `.env` supplies, and conftest's autouse `_hermetic_env` fixture
cannot reach back and rebuild it — by the time it scrubs ENV, the routes are
already registered. A plain route-absence assertion would therefore pass in CI
(no `.env`, so ENV defaults to production) and fail on a machine running
`ENV=development`, which is exactly the wrong way round for a guard rail. The
pure-function tests below run identically everywhere; the whole-app check is
the one that has to be conditional, and it is the one CI actually exercises.
"""

import pytest

from _src.config import ENV
from _src.main import app, docs_urls


def test_production_exposes_no_docs():
    assert docs_urls("production") == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


@pytest.mark.parametrize("env", ["", "prod", "Development", "staging", "test"])
def test_anything_but_development_fails_closed(env):
    """An unset, misspelled or renamed ENV must not serve docs.

    The check is `== "development"`, not `!= "production"`, precisely so that
    the failure mode of a typo is a missing dev convenience rather than a
    third-party script in production.
    """
    assert set(docs_urls(env).values()) == {None}


def test_development_serves_all_three_under_the_api_prefix():
    urls = docs_urls("development")
    assert None not in urls.values()
    # Everything not under /api is rewritten to the SPA by vercel.json, so a
    # route registered outside that prefix is one dev sees and production
    # cannot serve. FastAPI's own default for redoc — bare "/redoc" — is
    # exactly that mismatch, which is why it is overridden rather than left.
    for name, url in urls.items():
        assert url.startswith("/api/"), f"{name}={url} is outside the /api prefix"


def test_app_registers_nothing_docs_shaped_in_production():
    if ENV == "development":
        pytest.skip("app was imported with ENV=development; see module docstring")
    offenders = [
        path
        for route in app.routes
        for path in [getattr(route, "path", "")]
        if any(word in path for word in ("docs", "redoc", "openapi"))
    ]
    assert offenders == [], f"docs routes registered in production: {offenders}"


def test_app_wiring_agrees_with_docs_urls():
    """Catches the URLs being hardcoded back into the FastAPI() call."""
    known = {"/api/docs", "/api/redoc", "/api/openapi.json", "/docs", "/redoc", "/openapi.json"}
    registered = {getattr(r, "path", "") for r in app.routes} & known
    assert registered == {u for u in docs_urls(ENV).values() if u is not None}
