import asyncio
import logging
import os
import secrets
import ssl
import time
from urllib.parse import urlsplit

import sentry_sdk

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import DEV_FRONTEND_ORIGIN, ENV, SENTRY_DSN, current_env
from .db import get_db
from .monitoring import init_monitoring
from .routers import (
    expenses,
    groups,
    invitations,
    reports,
    settlements,
    unsubscribe,
    users,
)

# Before the app exists, not after: the Starlette integration patches the class,
# so an app constructed first would never be instrumented. A no-op without a
# DSN, which is the state in tests and under a local uvicorn.
init_monitoring()

logger = logging.getLogger("splitdec.health")


def docs_urls(env: str) -> dict[str, str | None]:
    """Interactive API docs, and the schema that feeds them: development only.

    FastAPI's Swagger page loads `swagger-ui-bundle.js` from cdn.jsdelivr.net at
    an unpinned major version and with no SRI. Served from `/api/docs`, that is
    a third-party script executing on the app's *own* origin — the origin whose
    localStorage holds the Supabase session — so in production the routes are
    not registered at all rather than merely being undocumented. `openapi_url`
    goes with it: it is what the page fetches, and on its own it enumerates
    every endpoint and schema in the API.

    `redoc_url` too, which FastAPI would otherwise default to `/redoc`. Note
    where that sits: *outside* the `/api` prefix, so today it is unreachable in
    production only because `vercel.json`'s catch-all rewrite sends it to the
    SPA before the function ever sees it. That is routing luck, not a decision,
    and it would evaporate the day the rewrite changes.

    Gated rather than deleted — like the CORS middleware below — because the
    docs are genuinely useful against a local uvicorn. Anything that is not
    exactly "development" gets nothing, so an unset or misspelled ENV fails
    closed.
    """
    if env == "development":
        return {
            "docs_url": "/api/docs",
            "redoc_url": "/api/redoc",
            "openapi_url": "/api/openapi.json",
        }
    return {"docs_url": None, "redoc_url": None, "openapi_url": None}


app = FastAPI(title="SplitDec API", **docs_urls(ENV))

# CORS is a local-dev-only concern: in production the SPA and the API are
# served same-origin under one Vercel domain (spec §1). Never enable this
# middleware outside development.
if ENV == "development":
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[DEV_FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def store_nothing(request: Request, call_next):
    """`Cache-Control: no-store` on everything this API answers.

    Nothing here set a caching header at all, which does not mean "do not
    cache" — it means the browser decides. Every authenticated GET in this app
    returns somebody's ledger: balances, what an expense was for, the email
    address of everyone in the group. On a shared or borrowed machine that is
    a copy left in the profile's disk cache after the session is gone, and
    nothing in a sign-out clears it.

    Shared caches were never the exposure — a proxy may not store a response
    to a request carrying `Authorization` (RFC 9111 §3.5), and in production
    the only thing between the browser and the function is Vercel, which is
    not caching a rewrite it was never asked to. The local disk is.

    `no-store` alone, deliberately. `private` says less and says it to
    intermediaries that were already excluded; `Pragma: no-cache` is a request
    header that HTTP/1.0 clients sent, and has no defined meaning on a
    response. The service worker is handled where it is configured
    (`vite.config.ts`: `navigateFallbackDenylist`, and no runtime caching
    rule matches `/api/`), because a header cannot reach a cache the page
    fills itself.

    One response is **not** covered, and it is worth naming rather than
    leaving for someone to find. Starlette puts `ServerErrorMiddleware`
    *outside* every user middleware and `ExceptionMiddleware` inside, so an
    `HTTPException` comes back through here and gets the header, while an
    exception nobody handled propagates past `call_next` and its 500 is
    written above us. That is acceptable on its own terms rather than by
    luck: the body of that response is the string "Internal Server Error",
    it carries nothing from the request, and a 5xx with no freshness header
    is not cached by browsers anyway. The alternative is a catch-all
    `Exception` handler, which sits in the middle of Sentry's capture path
    for the sake of a response with nothing in it.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


app.include_router(users.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(invitations.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(settlements.router, prefix="/api")
# Unauthenticated by necessity — browsers post violation reports with no
# credentials. It touches no database and stores nothing; see the module.
app.include_router(reports.router, prefix="/api")
# Also unauthenticated by necessity, and the only one of the two that writes:
# the person unsubscribing from invitation email has no account, which is the
# reason they want it stopped. A signed token is the whole authorization.
app.include_router(unsubscribe.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


def require_health_key(presented: str | None, probe: str) -> None:
    """The gate in front of every diagnostic route below.

    Outside development the key must be configured AND presented — a missing
    key means 503, never open access. Env read at call time for testability.
    """
    expected = os.getenv("HEALTH_PROBE_KEY", "")
    if not expected:
        if current_env() != "development":
            # Generic on the wire, specific in the log: these routes are
            # reachable by anyone, and naming the variable that switches them
            # on tells a stranger what to go looking for.
            logger.warning("%s probe refused: HEALTH_PROBE_KEY is not configured", probe)
            raise HTTPException(status_code=503, detail="Service unavailable")
        return
    # Constant-time: a plain `!=` leaks the shared secret one character at a
    # time. Compared as bytes because compare_digest rejects non-ASCII str,
    # and header values arrive latin-1 decoded.
    if not secrets.compare_digest(
        (presented or "").encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Health-Key")


@app.get("/api/health/db")
async def health_db(
    db: AsyncSession = Depends(get_db),
    x_health_key: str | None = Header(default=None, alias="X-Health-Key"),
):
    """Round-trip through the database; used to measure connect+query latency.

    Every call opens a fresh pooler connection (NullPool), so this is never
    open to the public — see `require_health_key`.
    """
    require_health_key(x_health_key, "Database")
    started = time.perf_counter()
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db_ms": round((time.perf_counter() - started) * 1000, 1)}


async def ingest_handshake(host: str, timeout: float = 5.0) -> str:
    """`"ok"`, or the exception that stopped a TLS handshake with `host`.

    Deliberately separate from the SDK. Sentry's transport swallows its own
    delivery failures, so asking it whether it worked is asking the one party
    that cannot say; this opens the connection itself and reports what
    happened. It writes nothing and reads nothing — the handshake completing
    is the entire answer.

    The host is taken from `SENTRY_DSN`, never from the request, so there is
    nothing here a caller could point at a third party.
    """
    try:
        connection = asyncio.open_connection(host, 443, ssl=ssl.create_default_context())
        _, writer = await asyncio.wait_for(connection, timeout)
    except Exception as exc:  # noqa: BLE001 — the exception *is* the result
        return f"{type(exc).__name__}: {exc}"
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return "ok"


@app.get("/api/health/sentry")
async def health_sentry(
    x_health_key: str | None = Header(default=None, alias="X-Health-Key"),
):
    """Is error reporting from this function actually reaching Sentry?

    It exists because nothing else can answer that. A failed send writes no
    log line — the transport records the lost event and re-raises into
    `capture_internal_exceptions()`, which swallows it — so a Sentry project
    that has never received anything from production is indistinguishable
    from an app that has never thrown. That was the real state here for the
    first three months: the only event `splitdec-api` held was a smoke test
    run from a laptop, while the function logged `SSLEOFError` against
    `/envelope/` every few minutes and said nothing about giving up.

    Two independent answers, because they fail for different reasons and the
    difference is the whole diagnosis. `tls` is this function reaching the
    ingest host at all, measured directly. `event_id` is the SDK's own path
    end to end — look that id up in Sentry, and if it is there, reporting
    works. The flush is what makes the second one meaningful: the worker
    sends on a background thread, and without waiting the platform can freeze
    the instance before the envelope leaves.

    Gated like the database probe, and for a better reason than symmetry: it
    names the ingest host and returns raw connection errors.
    """
    require_health_key(x_health_key, "Sentry")
    if not SENTRY_DSN:
        # Not an error. No DSN is how dev, CI and vitest stay out of the issue
        # stream (monitoring.py), so the honest answer is that there is
        # nothing configured to test.
        return {"dsn_configured": False, "ingest_host": None, "tls": None, "event_id": None}
    host = urlsplit(SENTRY_DSN).hostname or ""
    tls = await ingest_handshake(host)
    event_id = sentry_sdk.capture_message(
        "SplitDec Sentry reachability probe", level="error"
    )
    # Blocking, so off the event loop: the SDK's flush waits on a background
    # worker thread and would otherwise stall every other request this
    # instance is serving.
    await asyncio.to_thread(sentry_sdk.flush, 5.0)
    return {
        "dsn_configured": True,
        "ingest_host": host,
        "tls": tls,
        "event_id": event_id,
    }
