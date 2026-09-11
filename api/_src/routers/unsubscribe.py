"""The one-click unsubscribe endpoint for invitation email.

Unauthenticated by necessity: the person it exists for has no SplitDec account,
which is the whole reason they want the mail to stop. The token in the query
string is therefore the entire authorization, and it is an HMAC nobody can
forge without the deployment's secret (unsubscribe.py).

**There is no GET here, deliberately.** `List-Unsubscribe-Post` means a mail
provider POSTs this URL with no human involved (RFC 8058), while link scanners
and mail clients prefetch every GET they find in a message -- so a GET that
unsubscribed would fire on delivery, before the reader had done anything. The
human-facing page is `/unsubscribe` in the SPA, which explains what is about to
happen and then POSTs here.

This is the second route on the API a stranger can reach without a token, after
`/api/csp-report`, and it is the first one that writes. Three things bound what
that is worth: the signature, which makes a row keyed to nothing impossible; a
primary key, which makes the write idempotent rather than unbounded -- the same
address arriving a thousand times is one row; and the per-process token bucket
below. The bucket is a floor and not a ceiling for the reason spelled out at
length in reports.py: this is a serverless function with several instances that
cannot see each other's counters. The edge is where a ceiling would go.
"""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..unsubscribe import UNSUBSCRIBE_SECRET, suppress, verify_token

logger = logging.getLogger("splitdec.unsubscribe")

router = APIRouter(tags=["unsubscribe"])

# A real person unsubscribes once. This is sized for a mail provider retrying a
# one-click POST and for a page someone double-clicks, not for traffic.
REQUESTS_PER_MINUTE = 30

# Module-level and mutated without a lock, like the bucket in reports.py: the
# helper has no `await` in it, so within one event loop it runs to completion.
_tokens = float(REQUESTS_PER_MINUTE)
_last_refill = time.monotonic()


def _take_token() -> bool:
    global _tokens, _last_refill
    now = time.monotonic()
    _tokens = min(
        float(REQUESTS_PER_MINUTE),
        _tokens + (now - _last_refill) * (REQUESTS_PER_MINUTE / 60.0),
    )
    _last_refill = now
    if _tokens < 1.0:
        return False
    _tokens -= 1.0
    return True


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(
    token: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Stop sending invitation email to the address this token names.

    Idempotent: unsubscribing twice succeeds twice. A provider that retries a
    one-click POST, or a reader who presses the button again a month later,
    must not be told something went wrong.

    The token is verified before the session touches the database, so a request
    carrying a forged one never checks out a pooler connection.
    """
    if not _take_token():
        raise HTTPException(status_code=429, detail="Too many requests")
    if not UNSUBSCRIBE_SECRET:
        # Generic to the caller, specific in the log: an anonymous 500 naming
        # an environment variable hands a stranger the deployment's shape, and
        # this is the same reasoning auth.py applies to its own missing config.
        logger.error("UNSUBSCRIBE_SECRET is not set; cannot honour an opt-out")
        raise HTTPException(
            status_code=503, detail="Unsubscribe is temporarily unavailable"
        )
    recipient_hash = verify_token(token)
    if recipient_hash is None:
        # No oracle: a token cannot be constructed without the secret, so
        # "this one does not verify" tells a caller nothing they did not
        # already know about the link they are holding.
        raise HTTPException(status_code=400, detail="This unsubscribe link is not valid")
    await suppress(db, recipient_hash)
    await db.commit()
