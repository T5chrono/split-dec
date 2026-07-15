"""Local-dev bootstrap for `npm run api`, wired in via uvicorn --loop.

uvicorn calls this factory in the server process before importing the app,
which makes it the one dev-only hook where the process environment can be
sanitized. Two things on this machine otherwise break every authenticated
request (see the giant OPENSSL_Uplink/no OPENSSL_Applink crash):

- Norton's TLS inspection injects SSLKEYLOGFILE into every process. CPython's
  ssl module honors it, and the uv-managed interpreter's statically linked
  OpenSSL aborts the entire process when asked to open that file. Drop it.
- Norton also man-in-the-middles outbound HTTPS (e.g. the Supabase JWKS fetch
  in auth.py) with a CA certificate that OpenSSL 3.5 rejects as malformed.
  truststore makes Python validate TLS against the Windows certificate store
  instead, exactly like a browser — verification still happens, via the OS.

The selector loop keeps psycopg usable as an alternative local driver (its
async mode refuses Windows' default ProactorEventLoop); asyncpg runs on
either loop. Production (Vercel, Linux) never imports this module.
"""

import asyncio
import os
import selectors
import sys


def dev_loop_factory() -> asyncio.AbstractEventLoop:
    os.environ.pop("SSLKEYLOGFILE", None)
    try:
        import truststore

        truststore.inject_into_ssl()
    except ImportError:
        print(
            "dev_loop: truststore not installed (pip install -r requirements-dev.txt); "
            "outbound HTTPS may fail behind TLS-inspecting antivirus",
            file=sys.stderr,
        )
    return asyncio.SelectorEventLoop(selectors.SelectSelector())
