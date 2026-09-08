import ssl
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from .config import DATABASE_URL
from .supabase_ca import SUPABASE_ROOT_2021_CA_PEM

# Engine is created once at module scope and reused across warm invocations.
# NullPool: PgBouncer (Supabase Transaction Pooler, port 6543) does all pooling.
#
# The prepared-statement connect_args are asyncpg-specific (production driver):
# transaction-mode pooling can't use server-side prepared statements, so
# statement_cache_size=0 disables them (prepared_statement_cache_size=0 is a
# secondary safeguard). psycopg — usable for local dev on setups where
# asyncpg's TLS stack won't build — takes no such args, so only pass them for
# asyncpg.
_USES_ASYNCPG = "+asyncpg" in DATABASE_URL

_connect_args: dict[str, int] = {}
if _USES_ASYNCPG:
    _connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@lru_cache(maxsize=1)
def tls_context() -> ssl.SSLContext:
    """The TLS settings every database connection is made under.

    asyncpg's default is `sslmode=prefer`, and `prefer` means two things worth
    saying plainly. It will fall back to an unencrypted connection if the
    server answers that it does not do TLS — which an on-path attacker can
    answer on the server's behalf, since that answer arrives before any
    encryption exists. And when TLS *is* negotiated, asyncpg builds a context
    with `check_hostname = False` and `verify_mode = CERT_NONE`: any
    certificate at all is accepted, including one the attacker minted a second
    ago. Either way the `splitdec_app` password and every row of the ledger are
    readable by whoever is in the middle. `sslmode=require` closes only the
    first half; it is the same unverified context.

    So the connection carries a context of our own. `create_default_context()`
    is already verify-full — `check_hostname = True`, `CERT_REQUIRED`, the
    system trust store — and passing an `SSLContext` also stops asyncpg from
    falling back to plaintext, because a context is not a "prefer".

    The Supabase root is loaded *on top of* the system store rather than
    instead of it. It has to be there at all because the pooler presents a
    certificate from Supabase's own 2021 CA, which no public bundle carries —
    `ssl="verify-full"` fails for a second reason, incidentally: asyncpg reads
    that as libpq would and goes looking for `~/.postgresql/root.crt`. And the
    system store stays because it is what keeps this working on the day
    Supabase moves the pooler to a publicly trusted certificate, which would
    otherwise be an outage recoverable only by a deploy.

    `VERIFY_X509_STRICT` is cleared, and that is not tidying — it is the one
    line here that decides whether the app connects at all. Supabase's
    intermediate ("Supabase Intermediate 2021 CA") carries
    `basicConstraints: CA:TRUE` and **no `keyUsage` extension**, which RFC 5280
    says a CA certificate should have, so strict verification refuses the
    chain. Python 3.13 turned that flag on inside `create_default_context()`,
    which means leaving it alone makes this work or not work depending on the
    interpreter: fine on the 3.12 Vercel runs today, an outage on the day
    `.python-version` moves, and already broken on a maintainer's 3.14. Cleared
    explicitly, every version behaves the same. What is given up is conformance
    pedantry about a certificate we have pinned by hand — the signature, the
    chain to a trusted root, the expiry and the hostname are all still checked.

    Built lazily and cached, not at import. Creating an `SSLContext` is the
    kind of thing that goes wrong per-machine — on this one it aborts the
    interpreter outright while Norton's `SSLKEYLOGFILE` is set (see
    dev_loop.py) — and an import-time context would take the whole test suite
    down with it on a machine that never opens a socket.
    """
    context = ssl.create_default_context()
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    context.load_verify_locations(cadata=SUPABASE_ROOT_2021_CA_PEM)
    return context


if _USES_ASYNCPG:
    # Attached as a connect-time hook rather than passed in `connect_args`,
    # which is evaluated when the engine is built — see tls_context's last
    # paragraph. asyncpg reads `ssl` out of the connection kwargs, so mutating
    # them here is the same thing arriving later.
    @event.listens_for(engine.sync_engine, "do_connect")
    def _verify_the_server(dialect, conn_rec, cargs, cparams) -> None:
        cparams["ssl"] = tls_context()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
