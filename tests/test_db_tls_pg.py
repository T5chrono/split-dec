"""Optional integration test: the live pooler's certificate actually verifies.

`tests/test_db_tls.py` checks that the context we build is strict. Nothing in
it checks the other half — that the server on the far end presents a chain that
context accepts. Those are different claims, and getting the second one wrong
is not a failing test but an outage: every request fails at connect time, and
the only way back is a deploy.

So this is the gate in front of a change to `api/_src/db.py` or
`api/_src/supabase_ca.py`. It reads nothing, writes nothing and needs no
privileges — it opens a connection and closes it — which is why it takes
`AUDIT_DATABASE_URL` and is *meant* to be pointed at production, exactly like
`tests/test_grants_pg.py`:

    AUDIT_DATABASE_URL='postgresql+asyncpg://postgres.<ref>:<pw>@...:6543/postgres' \
      python -m pytest tests/test_db_tls_pg.py -v

Run it again whenever the certificate changes hands — Supabase's 2021 root
expires in April 2031, and a rotation before then arrives as a connection
failure rather than a warning (`docs/supply-chain.md`).

Unlike the other Postgres tests this one can survive the antivirus problem on
its own: the `SSLKEYLOGFILE` that aborts the interpreter is read when a context
is created, and the fixture below drops it first. `truststore` is not needed —
`db.tls_context()` reads the Windows store through `create_default_context()`.
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from _src import db

AUDIT_DATABASE_URL = os.getenv("AUDIT_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not AUDIT_DATABASE_URL, reason="AUDIT_DATABASE_URL not set"
)


@pytest.fixture
def strict_tls(monkeypatch):
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    db.tls_context.cache_clear()
    try:
        yield db.tls_context()
    finally:
        db.tls_context.cache_clear()


async def test_the_pooler_passes_verification(strict_tls):
    """A full-strength handshake against the real host: the chain has to
    resolve to something we trust *and* the certificate has to be for the
    hostname in the DSN. A failure here means the deployment would not have
    come up."""
    if "+asyncpg" not in AUDIT_DATABASE_URL:
        pytest.skip("TLS settings here are asyncpg's")
    engine = create_async_engine(
        AUDIT_DATABASE_URL,
        poolclass=NullPool,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "ssl": strict_tls,
        },
    )
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("SELECT 1"))).scalar() == 1
    finally:
        await engine.dispose()
