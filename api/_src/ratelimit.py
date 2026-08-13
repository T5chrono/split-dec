"""Volume brakes on the endpoints that create rows.

Every limit here counts rows already in the database rather than keeping
counters in process memory: the API is a single Vercel function that scales to
several concurrent instances and cold-starts constantly, so in-process state
would be both unshared and routinely lost. The database is the only counter
all instances agree on.

What it counts is `write_events` — one append-only row per quota-consuming
write, charged to the caller — and not the expenses, settlements, groups and
invitations being created. Counting those made every window resettable.
Soft-deleted and cancelled rows did still count, but deleting a *group* is a
hard delete that takes its expenses, settlements and invitations with it
(routers/groups.py), and any member may delete a group once it is settled:
create a group, fill it, delete it, repeat, and every window was clear again.
A tombstone that nothing cascades to is what closes that loop.

Moving the count off those tables also put the ledger window on its natural
axis. It was per-group, so one member could consume the allowance of everyone
else in the group; the ledger and group windows are both per-caller now.

Recording an event *is* the slot being spent, so it happens exactly once, in
the same transaction as the row it authorizes. A create that rolls back — the
idempotency race in expenses.py, the concurrent-duplicate race in
invitations.py, or a validation failure after the check — takes its event with
it, and a replay is answered before the quota is ever consulted, because a
client retrying a request whose response it never saw has already paid for that
slot.

Deliberately no global cap on the ledger or group windows: a deployment-wide
ceiling would turn one abusive account into an outage for everybody.
Invitations do carry one, because the resource they burn — the sending
domain's reputation — is shared and cannot be bought back.
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WriteEvent

# The kinds of slot. Kept apart so a burst of expenses cannot exhaust the
# allowance for creating a group or sending an invitation.
LEDGER = "LEDGER"
GROUP = "GROUP"
INVITE = "INVITE"

WRITE_WINDOW = timedelta(hours=24)

# Expenses + settlements combined, per caller. One person logging every meal on
# a busy trip might reach 50 in a day across all their groups; this leaves room
# for that and still stops a runaway client well short of any real damage.
MAX_LEDGER_WRITES_PER_CALLER = 100

# Groups one account can create in a window. Nobody legitimately creates 25
# groups a day.
MAX_GROUPS_PER_CALLER = 25

# Every invitation to a non-member triggers an outbound email, and cancelling
# one frees its (group, email) slot immediately — so without quotas a single
# account can drive an unbounded invite/cancel loop at any address and burn the
# sending domain's reputation, which is the one resource here that money cannot
# buy back.
INVITE_WINDOW = timedelta(hours=24)
INVITE_MAX_PER_INVITER = 20  # one person inviting, across all their groups
INVITE_MAX_PER_RECIPIENT = 3  # one address, however many accounts aim at it
INVITE_MAX_GLOBAL = 300  # whole-deployment brake on a compromised account


def window_cutoff(db: AsyncSession, window: timedelta = WRITE_WINDOW) -> datetime:
    """Start of a rate-limit window, in the flavour the bound dialect stores
    `created_at` as. Postgres keeps TIMESTAMPTZ; SQLite (tests) keeps the
    naive UTC text CURRENT_TIMESTAMP produces, and comparing that against an
    offset-aware bind parameter compares wrong."""
    cutoff = datetime.now(timezone.utc) - window
    if db.get_bind().dialect.name == "sqlite":
        return cutoff.replace(tzinfo=None)
    return cutoff


def recipient_key(email: str) -> str:
    """Match-only identifier for an invitation recipient.

    The per-recipient window asks one question — has *this* address already had
    its share today — which equality on a digest answers as well as the address
    would. Storing the digest instead keeps every contactable address out of a
    table that deliberately outlives the invitation, so account deletion can go
    on promising to erase the address (routers/users.py).

    Unpeppered on purpose rather than for show: anyone who can read this column
    can already read `public.users.email` in plaintext, so a pepper would buy
    nothing real while adding a secret to manage and a rotation that would
    silently reset every recipient window.
    """
    return hashlib.sha256(email.lower().encode()).hexdigest()


def _too_many(detail: str, window: timedelta = WRITE_WINDOW) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(int(window.total_seconds()))},
    )


async def _slots_used(db: AsyncSession, caller: uuid.UUID, kind: str) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(WriteEvent)
            .where(
                WriteEvent.user_id == caller,
                WriteEvent.kind == kind,
                WriteEvent.created_at >= window_cutoff(db),
            )
        )
    ).scalar_one()


async def record_write(
    db: AsyncSession, caller: uuid.UUID, kind: str, *, recipient: str | None = None
) -> None:
    """Charge one slot to the caller.

    Call it in the same transaction as the row it authorizes, so the two commit
    or roll back together. The event is added to the session rather than
    committed here — the endpoint owns the transaction.
    """
    # Opportunistic prune, scoped to this caller: rows that have aged out of
    # every window can never be counted again, and a serverless function has
    # nowhere to hang a cron. Usually deletes nothing, and the
    # (user_id, created_at) index makes finding that out cheap. Uses the
    # longest window so a shorter one can never sweep rows another still needs,
    # and runs before the insert below so it cannot sweep the row being
    # written. An INVITE row is charged to its inviter, so it is pruned on the
    # inviter's next write — no row is keyed only to someone who never writes.
    await db.execute(
        delete(WriteEvent).where(
            WriteEvent.user_id == caller,
            WriteEvent.created_at < window_cutoff(db, max(WRITE_WINDOW, INVITE_WINDOW)),
        )
    )
    db.add(
        WriteEvent(
            user_id=caller,
            kind=kind,
            recipient_hash=recipient_key(recipient) if recipient is not None else None,
        )
    )


async def enforce_ledger_write_quota(db: AsyncSession, caller: uuid.UUID) -> None:
    """429 once one account has created too many expenses + settlements.

    Counted across both endpoints and across every group the caller writes to.
    The message can name the caller's own activity: unlike the invitation
    quotas it reveals nothing about anyone else.
    """
    if await _slots_used(db, caller, LEDGER) >= MAX_LEDGER_WRITES_PER_CALLER:
        raise _too_many(
            "You have recorded too many entries recently. Please try again later."
        )


async def enforce_group_creation_quota(db: AsyncSession, caller: uuid.UUID) -> None:
    """429 once one account has created too many groups in the window."""
    if await _slots_used(db, caller, GROUP) >= MAX_GROUPS_PER_CALLER:
        raise _too_many("You have created too many groups recently. Please try again later.")


async def enforce_invitation_quota(
    db: AsyncSession, caller: uuid.UUID, email: str
) -> None:
    """429 once any of the three invitation windows is exhausted. One round trip."""
    by_caller, by_recipient, overall = (
        await db.execute(
            select(
                func.sum(case((WriteEvent.user_id == caller, 1), else_=0)),
                func.sum(
                    case((WriteEvent.recipient_hash == recipient_key(email), 1), else_=0)
                ),
                func.count(),
            ).where(
                WriteEvent.kind == INVITE,
                WriteEvent.created_at >= window_cutoff(db, INVITE_WINDOW),
            )
        )
    ).one()
    exceeded = (
        (by_caller or 0) >= INVITE_MAX_PER_INVITER
        or (by_recipient or 0) >= INVITE_MAX_PER_RECIPIENT
        or overall >= INVITE_MAX_GLOBAL
    )
    if exceeded:
        # Deliberately one message for all three limits: which limit was hit
        # would tell the caller whether someone else has been inviting this
        # address, and the global one would report deployment-wide activity.
        raise _too_many(
            "Too many invitations sent recently. Please try again later.", INVITE_WINDOW
        )
