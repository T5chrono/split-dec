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
cannot see each other's counters.

**The ceiling is at the edge**: a Vercel Firewall rule named "Unsubscribe flood
limit", `path equals /api/unsubscribe`, 30 requests per 60s keyed by IP, denying
for 5m. It lives in the Vercel project, invisible from here and from CI
(`vercel firewall rules list`). The number matches `REQUESTS_PER_MINUTE` on
purpose and is not lower: RFC 8058 one-click POSTs come from the mail
provider's servers, so many recipients share a handful of IPs. If the number
below changes, change the rule too.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..token_bucket import TokenBucket
from ..unsubscribe import UNSUBSCRIBE_SECRET, suppress, verify_token

logger = logging.getLogger("splitdec.unsubscribe")

router = APIRouter(tags=["unsubscribe"])

# A real person unsubscribes once. This is sized for a mail provider retrying a
# one-click POST and for a page someone double-clicks, not for traffic. The
# Firewall rule in the module docstring carries the same number; change both.
REQUESTS_PER_MINUTE = 30

# Refusals are logged once per drought: before the shared helper existed this
# route answered 429 and said nothing, so a flood left no trace.
_bucket = TokenBucket(
    REQUESTS_PER_MINUTE, logger, "unsubscribe requests refused: rate limit reached"
)


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
    if not _bucket.take():
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
