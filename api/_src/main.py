from fastapi import FastAPI

from .config import DEV_FRONTEND_ORIGIN, ENV
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
