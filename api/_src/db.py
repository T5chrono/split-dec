from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import DATABASE_URL

# Engine is created once at module scope and reused across warm invocations.
# NullPool: PgBouncer (Supabase Transaction Pooler, port 6543) does all pooling.
#
# The prepared-statement connect_args are asyncpg-specific (production driver):
# transaction-mode pooling can't use server-side prepared statements, so
# statement_cache_size=0 disables them (prepared_statement_cache_size=0 is a
# secondary safeguard). psycopg — usable for local dev on setups where
# asyncpg's TLS stack won't build — takes no such args, so only pass them for
# asyncpg.
_connect_args: dict[str, int] = {}
if "+asyncpg" in DATABASE_URL:
    _connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
