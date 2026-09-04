import logging
import os
import secrets
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import DEV_FRONTEND_ORIGIN, ENV, current_env
from .db import get_db
from .monitoring import init_monitoring
from .routers import expenses, groups, invitations, reports, settlements, users

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

app.include_router(users.router, prefix="/api")
app.include_router(groups.router, prefix="/api")
app.include_router(invitations.router, prefix="/api")
app.include_router(expenses.router, prefix="/api")
app.include_router(settlements.router, prefix="/api")
# Unauthenticated by necessity — browsers post violation reports with no
# credentials. It touches no database and stores nothing; see the module.
app.include_router(reports.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_db(
    db: AsyncSession = Depends(get_db),
    x_health_key: str | None = Header(default=None, alias="X-Health-Key"),
):
    """Round-trip through the database; used to measure connect+query latency.

    Every call opens a fresh pooler connection (NullPool), so this is never
    open to the public: outside development it requires HEALTH_PROBE_KEY to
    be configured AND presented — a missing key means 503, not open access.
    Env read at call time for testability.
    """
    expected = os.getenv("HEALTH_PROBE_KEY", "")
    if not expected:
        if current_env() != "development":
            # Generic on the wire, specific in the log: this route is reachable
            # by anyone, and naming the variable that switches it on tells a
            # stranger what to go looking for.
            logger.warning("Database probe refused: HEALTH_PROBE_KEY is not configured")
            raise HTTPException(status_code=503, detail="Service unavailable")
    # Constant-time: a plain `!=` leaks the shared secret one character at a
    # time. Compared as bytes because compare_digest rejects non-ASCII str,
    # and header values arrive latin-1 decoded.
    elif not secrets.compare_digest(
        (x_health_key or "").encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Health-Key")
    started = time.perf_counter()
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db_ms": round((time.perf_counter() - started) * 1000, 1)}
