from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import DATABASE_URL

# Engine is created once at module scope and reused across warm invocations.
# NullPool: PgBouncer (Supabase Transaction Pooler, port 6543) does all pooling.
# statement_cache_size=0: transaction-mode pooling does not support server-side
# prepared statements; prepared_statement_cache_size=0 is a secondary safeguard.
engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
