import os

try:  # convenience for local dev; python-dotenv is not required in production
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ENV = os.getenv("ENV", "production")

# Supabase Transaction Pooler URL (port 6543), e.g.
# postgresql+asyncpg://postgres.<ref>:<password>@aws-0-eu-west-3.pooler.supabase.com:6543/postgres
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Public project URL; used for JWKS token verification. Env can override.
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://kmlheefyzhhegxmtaovq.supabase.co")
# Legacy HS256 JWT secret (Project Settings -> API -> JWT Secret).
# If the project uses asymmetric signing keys instead, leave this unset and
# the backend verifies tokens against the project's JWKS endpoint.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

DEV_FRONTEND_ORIGIN = os.getenv("DEV_FRONTEND_ORIGIN", "http://localhost:5173")
