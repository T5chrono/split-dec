"""Nothing this API answers may be written to disk by the client.

Every authenticated response here is somebody's ledger — balances, what an
expense was for, who is in the group and at which address. With no
`Cache-Control` at all the browser decides, and what it decides is stored in a
profile that outlives the session.
"""

import pathlib

import pytest
from httpx import ASGITransport, AsyncClient

from _src.main import app


@pytest.fixture
async def anonymous_client():
    """No dependency overrides: the real `verify_jwt` answers, so this reaches
    the 401 path rather than an endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_an_authenticated_read_is_not_stored(client, two_user_group):
    response = await client.get("/api/groups")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"


async def test_a_refusal_is_not_stored_either(anonymous_client):
    """A 401 body says little, but a rule that holds only on the success path
    is one route away from being wrong. Every deliberate refusal in this
    codebase is an `HTTPException`, and those come back through the
    middleware; the uncovered case is an exception nobody handled, whose 500
    Starlette writes outside us and which carries nothing from the request
    (see `store_nothing`)."""
    response = await anonymous_client.get("/api/groups")
    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"


async def test_nothing_else_is_claimed(anonymous_client):
    """`private` addresses shared caches, which RFC 9111 §3.5 already bars from
    storing a response to an `Authorization` request; `Pragma` is a *request*
    header with no defined meaning here. Both read as caution and neither adds
    a rule."""
    response = await anonymous_client.get("/api/health")
    assert response.headers["cache-control"] == "no-store"
    assert "pragma" not in response.headers


def test_the_service_worker_does_not_cache_the_api():
    """The other local store, and the one a header cannot reach: an installed
    PWA's Cache Storage is filled by the page, not by the browser's own rules.
    Workbox is told to keep out of `/api/` in `vite.config.ts`; assert it here
    because nothing else does."""
    config = (pathlib.Path(__file__).resolve().parents[1] / "vite.config.ts").read_text(
        encoding="utf-8"
    )
    assert r"navigateFallbackDenylist: [/^\/api\//]" in config
    assert "runtimeCaching" not in config
