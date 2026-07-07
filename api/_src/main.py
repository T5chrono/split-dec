import os
import time

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .config import DEV_FRONTEND_ORIGIN, ENV
from .db import get_db
from .routers import expenses, groups, invitations, settlements, users

app = FastAPI(title="SplitDec API", docs_url="/api/docs", openapi_url="/api/openapi.json")

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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/health/db")
async def health_db(
    db: AsyncSession = Depends(get_db),
    x_health_key: str | None = Header(default=None, alias="X-Health-Key"),
):
    """Round-trip through the database; used to measure connect+query latency.

    Every call opens a fresh pooler connection (NullPool), so when
    HEALTH_PROBE_KEY is configured the probe demands it — an unauthenticated
    free lever on pooler slots otherwise. Read at call time for testability.
    """
    expected = os.getenv("HEALTH_PROBE_KEY", "")
    if expected and x_health_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Health-Key")
    started = time.perf_counter()
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db_ms": round((time.perf_counter() - started) * 1000, 1)}
