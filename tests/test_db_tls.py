"""How the database connection decides who it is talking to.

asyncpg left to itself accepts any certificate and will drop to plaintext if
something claims the server does not speak TLS, so the pooler password and the
whole ledger are readable by anyone on the path between the function and the
database. `_src.db` replaces that with a context of our own; these tests are
what stop a later edit quietly handing the decision back.
"""

import base64
import hashlib
import ssl

import pytest
from sqlalchemy import event

from _src import db
from _src.supabase_ca import SUPABASE_ROOT_2021_CA_PEM

# The root observed on the live pooler, recorded in supabase_ca.py. Pinned here
# as well so swapping the certificate is a failing test rather than a silent
# change of who the deployment trusts.
SUPABASE_ROOT_SHA256 = (
    "807025AD50D4ED219D2C9C7D299C004F824EB00CF7F65AFEF607D07B72E6CAFA"
)


@pytest.fixture
def context(monkeypatch) -> ssl.SSLContext:
    # Norton injects SSLKEYLOGFILE, and this Python aborts the whole process
    # when OpenSSL opens that path — building any SSLContext, not just this
    # one. Dropped for the test the same way dev_loop.py drops it to run the
    # server. See CLAUDE.md; on CI and on Vercel the variable is not set.
    monkeypatch.delenv("SSLKEYLOGFILE", raising=False)
    db.tls_context.cache_clear()
    try:
        yield db.tls_context()
    finally:
        db.tls_context.cache_clear()


def test_the_certificate_is_verified(context):
    assert context.check_hostname is True
    assert context.verify_mode is ssl.CERT_REQUIRED


def test_rfc_5280_pedantry_is_off(context):
    """Not a stray relaxation: Supabase's *intermediate* declares itself a CA
    and carries no `keyUsage` extension, so strict verification refuses the
    whole chain. Python 3.13 turned that flag on by default, so leaving it
    alone would make connecting work or fail depending on the interpreter —
    fine on the 3.12 Vercel runs, an outage the day that pin moves. Signature,
    chain, expiry and hostname are all still verified."""
    assert not context.verify_flags & ssl.VERIFY_X509_STRICT


def test_supabase_is_trusted(context):
    """The pooler's certificate chains to Supabase's own 2021 root, which is in
    no public bundle — without this the connection cannot be made at all."""
    subjects = {
        name
        for cert in context.get_ca_certs()
        for rdn in cert.get("subject", ())
        for key, name in rdn
        if key == "commonName"
    }
    assert "Supabase Root 2021 CA" in subjects


def test_the_public_roots_are_trusted_too(context):
    """Loaded alongside, not instead of. The day Supabase moves the pooler onto
    a publicly trusted certificate this keeps working; pinning to their root
    alone would turn that into an outage only a deploy could end."""
    assert len(context.get_ca_certs()) > 1


def test_the_embedded_root_is_the_one_that_was_audited():
    der = base64.b64decode(
        "".join(
            line
            for line in SUPABASE_ROOT_2021_CA_PEM.splitlines()
            if "CERTIFICATE" not in line
        )
    )
    assert hashlib.sha256(der).hexdigest().upper() == SUPABASE_ROOT_SHA256


def test_every_connection_gets_the_context(context):
    """The hook is what actually attaches it. `connect_args` would be evaluated
    when the engine is built, which is import time — too early to create an
    SSLContext safely, and early enough to take the test suite with it."""
    assert event.contains(db.engine.sync_engine, "do_connect", db._verify_the_server)
    cparams: dict[str, object] = {}
    db._verify_the_server(None, None, (), cparams)
    assert cparams["ssl"] is context


def test_the_connection_never_settles_for_a_bare_sslmode():
    """`ssl="require"` and `?sslmode=require` both read as a fix and are not
    one: they stop the plaintext fallback and leave the same CERT_NONE context
    behind, so any certificate at all still passes."""
    assert "ssl" not in db._connect_args
    assert "sslmode" not in db.DATABASE_URL
