"""Recipient-controlled opt-out from invitation email.

Anyone with an account can invite any address, so the person who receives an
invitation is, in the general case, someone who has never used SplitDec and
agreed to nothing. The send quotas (ratelimit.py) bound how *often* that can
happen — three per address per day — but a rate limit is not an off switch, and
the only way to stop the mail outright used to be reporting it as spam. That
works, via the provider's own complaint suppression, at the exact cost the
global invitation quota exists to protect: the sending domain's reputation.

So there is a real one. The recipient follows a link (or presses their mail
client's own unsubscribe button, see `emailer.py`) and the address is recorded
here; `invite_to_group` then skips the provider call for it.

**Opting out stops the email and nothing else.** The invitation row is still
created, still counts against the sender's quota, and still appears in the app
if that person ever signs up. Silently dropping the invitation would break the
product for somebody who only ever said "stop writing to me", and *not*
charging the quota would turn the sender's own allowance into an oracle for
whether a given address has unsubscribed — the registration oracle that
`GET /users/search` was removed for, rebuilt out of a rate limit.

Three decisions here are load-bearing.

**The table is keyed by the unpeppered digest (`ratelimit.recipient_key`),
while the token is signed with a secret.** The tempting alternative — key the
table by an HMAC of the address, so a database reader cannot reverse it — makes
rotating the secret silently orphan every suppression row and resume emailing
people who opted out. A broken promise that nothing announces is worse than a
digest whose weakness is already written down, so rotation costs outstanding
*links* (a recipient can object again) and never the objections themselves.

Note this makes `recipient_key` durable in a way `write_events` is not: that
table is pruned after about a day, and its docstring leans on it. Rows here are
kept for as long as the objection stands, which is the point of them.

**Account deletion does not clear a suppression.** The row is a standing
instruction from whoever holds that mailbox, not a fact about a SplitDec
account, and erasing it on deletion would mean signing up and deleting again is
how you resume mail to an address that refused it. Keeping the record of an
objection is what honouring the objection requires.

**The token carries the digest, not the address.** It ends up in a URL, and
therefore in the function's request logs; a digest there is the same identifier
`write_events` already stores, and not something you can send mail to. The
address itself must never appear in either place.
"""

import base64
import hashlib
import hmac
import logging
import os

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EmailSuppression
from .ratelimit import recipient_key

logger = logging.getLogger("splitdec.unsubscribe")

# No default, and nothing falls back to a fixed string: a guessable secret here
# lets anyone unsubscribe any address they can name, which is a denial of the
# invitation email for arbitrary people. Absent, the feature degrades to the
# `mailto:` unsubscribe in emailer.py rather than to a forgeable link.
UNSUBSCRIBE_SECRET = os.getenv("UNSUBSCRIBE_SECRET", "")

# Domain separation, so the signature over a digest can never be confused with
# any other value this secret might one day authenticate.
_SIG_PREFIX = b"splitdec-unsubscribe-v1:"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes | None:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError):
        return None


def _sign(digest: bytes) -> bytes:
    return hmac.new(
        UNSUBSCRIBE_SECRET.encode(), _SIG_PREFIX + digest, hashlib.sha256
    ).digest()


def mint_token(email: str) -> str | None:
    """An unsubscribe capability for one address, or None with no secret set.

    `<digest>.<signature>`, both base64url. The digest is what the suppression
    table is keyed by; the signature is what stops a stranger posting an
    arbitrary 32 bytes and filling that table with rows keyed to nothing.
    """
    if not UNSUBSCRIBE_SECRET:
        return None
    digest = bytes.fromhex(recipient_key(email))
    return f"{_b64(digest)}.{_b64(_sign(digest))}"


def verify_token(token: str) -> str | None:
    """The `recipient_hash` a token authorizes, or None if it does not verify.

    Never raises on malformed input — this is reached by anyone who can make an
    HTTP request, and a token is whatever they put in the query string.
    """
    if not UNSUBSCRIBE_SECRET or not token or token.count(".") != 1:
        return None
    encoded_digest, encoded_sig = token.split(".")
    digest, signature = _unb64(encoded_digest), _unb64(encoded_sig)
    if digest is None or signature is None or len(digest) != 32:
        return None
    # Constant-time: a byte-by-byte comparison that short-circuits leaks how
    # much of a forged signature was right, which is enough to build the rest.
    if not hmac.compare_digest(_sign(digest), signature):
        return None
    return digest.hex()


async def suppress(db: AsyncSession, recipient_hash: str) -> None:
    """Record the objection. Idempotent — unsubscribing twice is not an error.

    Through a SAVEPOINT so the loser of a race rolls back its own INSERT
    instead of poisoning the transaction, and so this stays one statement on
    both dialects rather than a Postgres `ON CONFLICT` and a SQLite `OR
    IGNORE`. Same shape as `welcome.ensure_system_user`.
    """
    try:
        async with db.begin_nested():
            db.add(EmailSuppression(recipient_hash=recipient_hash))
    except IntegrityError:
        pass


async def is_suppressed(db: AsyncSession, email: str) -> bool:
    """Whether this address has asked not to receive invitation email.

    Read before `invite_to_group` commits, like the inviter and group names it
    sits beside: the provider call that follows must not be holding a pooler
    connection, and a read after the commit would have checked one out again.
    """
    return (
        await db.execute(
            select(EmailSuppression.recipient_hash).where(
                EmailSuppression.recipient_hash == recipient_key(email)
            )
        )
    ).scalar_one_or_none() is not None
