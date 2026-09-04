import os
import re

try:  # convenience for local dev; python-dotenv is not required in production
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def resolve_env(requested: str, vercel_env: str) -> str:
    """The environment the app actually runs as, not the one it was asked for.

    `ENV` is our own variable and a hosted deployment can be given any value
    for it — including `development`, which switches on the Swagger page (a
    third-party script on the origin holding the Supabase session), the CORS
    middleware, and the open database probe. Nothing was cross-checking that
    against where the code is actually running.

    `VERCEL_ENV` is set by the platform, not by us, and cannot be overridden
    from the project's environment variables. It reads `production` or
    `preview` on a hosted deployment and `development` only under a local
    `vercel dev`. So: whenever the platform says this is hosted and not
    development, `production` wins regardless of what `ENV` asked for.

    Unset `VERCEL_ENV` means nobody is claiming this is hosted — a laptop, CI,
    or pytest — and `ENV` is taken at its word. That is the one state where
    `development` is reachable, which is the point: an unknown or misspelled
    hosted state fails closed, exactly like `docs_urls` does.
    """
    if vercel_env and vercel_env != "development":
        return "production"
    return requested


def current_env() -> str:
    """`resolve_env` over the live environment. Read at call time, so a test
    can flip `ENV` on an already-imported module."""
    return resolve_env(os.getenv("ENV", "production"), os.getenv("VERCEL_ENV", ""))


ENV = current_env()

# Supabase Transaction Pooler URL (port 6543), e.g.
# postgresql+asyncpg://postgres.<ref>:<password>@aws-0-eu-west-3.pooler.supabase.com:6543/postgres
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Public project URL; used for JWKS token verification.
#
# Deliberately no default. It used to fall back to the production project,
# which meant a deployment that simply forgot the variable — a preview, a fork,
# a self-hosted copy — silently trusted tokens minted by *our* Supabase project
# while reading somebody else's database. The trust anchor for authentication
# is not a thing to guess: `supabase_url_problem` below refuses to verify
# anything until it is set, and cross-checks it against DATABASE_URL so the
# two cannot name different projects.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")

# Legacy HS256 JWT secret (Project Settings -> API -> JWT Secret), and the
# switch that has to be thrown before it is accepted at all. See auth.py: the
# project signs with asymmetric keys (its JWKS serves a single ES256 key), so
# the symmetric path is dead code in this deployment and is off unless somebody
# deliberately turns it back on.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
ALLOW_LEGACY_HS256 = os.getenv("ALLOW_LEGACY_HS256", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

DEV_FRONTEND_ORIGIN = os.getenv("DEV_FRONTEND_ORIGIN", "http://localhost:5173")

# Error reporting for the API function (see monitoring.py). Unset means the SDK
# is never initialised, which is what keeps local uvicorn runs and the test
# suite out of the issue stream — there is no second switch to forget.
# Unlike the browser DSN this one is not public: it is only in Vercel's env.
SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# Vercel sets these on every deployment. `VERCEL_ENV` is production / preview /
# development, which is a finer distinction than ENV makes and the one Sentry
# buckets by; the commit SHA is what pairs an event with the code that threw.
SENTRY_ENVIRONMENT = os.getenv("VERCEL_ENV", ENV)
SENTRY_RELEASE = os.getenv("VERCEL_GIT_COMMIT_SHA", "")

# `https://<ref>.supabase.co`, and the pooler DSN's `<role>.<ref>` username.
# Two shapes, one identifier: the project ref is the only thing that ties the
# token issuer to the database the tokens grant access to.
#
# The username half is `<role>.<ref>` for *any* role, not `postgres.<ref>`.
# That mattered the day the app stopped connecting as the owner
# (20260904100000): a hardcoded `postgres` stopped matching, project_ref
# returned None, and "no ref" reads as "nothing to compare" — so the check
# below would have gone quietly dead exactly when the production DSN changed.
# Role names cannot contain a dot here, which is also what stops a userless
# DSN's dotted *hostname* being read as a ref.
_PROJECT_URL = re.compile(r"^https://([a-z0-9]+)\.supabase\.(?:co|in)/?$")
_POOLER_DSN = re.compile(r"^[a-z0-9+.-]+://[a-z0-9_-]+\.([a-z0-9]+)[:@]")

# A database host that belongs to Supabase: the pooler
# (`aws-0-*.pooler.supabase.com`) or a direct `db.<ref>.supabase.co`. Used only
# to tell "there is no ref to compare" apart from "there should have been one".
_SUPABASE_DB_HOST = re.compile(
    r"@[a-z0-9.-]+\.supabase\.(?:com|co|in)(?=[:/]|$)", re.IGNORECASE
)


def project_ref(value: str) -> str | None:
    """The Supabase project ref inside a project URL or a pooler DSN.

    `None` for anything else — a direct `postgres://` connection to a local
    database has no ref, and that is not an error, just an absence.
    """
    if not value:
        return None
    value = value.strip()
    for pattern in (_PROJECT_URL, _POOLER_DSN):
        match = pattern.match(value)
        if match:
            return match.group(1)
    return None


def supabase_url_problem(supabase_url: str, database_url: str) -> str | None:
    """Why these two cannot be trusted together, or `None` if they can.

    Returned as a string rather than raised so the caller decides what the
    failure looks like — auth.py turns it into a generic 500 for the client and
    keeps the specifics in the server log.
    """
    if not supabase_url:
        return "SUPABASE_URL is not set"
    ref = project_ref(supabase_url)
    if ref is None:
        return "SUPABASE_URL is not a Supabase project URL"
    db_ref = project_ref(database_url)
    if db_ref is None:
        # No ref is normally an absence, not a conflict — a local Postgres has
        # none. But a Supabase host with no readable ref is the shape of this
        # check silently switching itself off, which is how a username change
        # nearly disabled it once. Refuse rather than skip.
        if _SUPABASE_DB_HOST.search(database_url):
            return (
                "DATABASE_URL names a Supabase host but no project ref could be "
                "read from it, so it cannot be checked against SUPABASE_URL"
            )
        return None
    if db_ref != ref:
        # The interesting failure: tokens verified against one project's keys
        # while every `sub` in them is looked up in another project's tables.
        return f"SUPABASE_URL names project {ref} but DATABASE_URL names {db_ref}"
    return None
