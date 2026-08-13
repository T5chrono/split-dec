"""Volume brakes on the endpoints that create rows.

Every limit here counts rows already in the database rather than keeping
counters in process memory: the API is a single Vercel function that scales to
several concurrent instances and cold-starts constantly, so in-process state
would be both unshared and routinely lost. The database is the only counter
all instances agree on.

What it counts is `write_events` — one append-only row per quota-consuming
write, charged to the caller — and not the expenses, settlements and groups
being created. Counting those made every window resettable. Soft-deleted
entries did still count, but deleting a *group* is a hard delete that takes its
expenses and settlements with it (routers/groups.py), and any member may delete
a group once it is settled: create a group, fill it, delete it, repeat, and
both windows were clear again. A tombstone that nothing cascades to is what
closes that loop.

Moving the count off the ledger tables also put the ledger window on its
natural axis. It was per-group, so one member could consume the allowance of
everyone else in the group; both windows are now per-caller.

Recording an event *is* the slot being spent, so it happens exactly once, in
the same transaction as the row it authorizes. A create that rolls back — the
idempotency race in expenses.py, or a validation failure after the check —
takes its event with it, and a replay is answered before the quota is ever
consulted, because a client retrying a request whose response it never saw has
already paid for that slot.

Deliberately no global cap on either window: a deployment-wide ceiling would
turn one abusive account into an outage for everybody.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WriteEvent

# The two kinds of slot. Kept apart so a burst of expenses cannot exhaust the
# allowance for creating a group, and vice versa.
LEDGER = "LEDGER"
GROUP = "GROUP"

WRITE_WINDOW = timedelta(hours=24)

# Expenses + settlements combined, per caller. One person logging every meal on
# a busy trip might reach 50 in a day across all their groups; this leaves room
# for that and still stops a runaway client.
MAX_LEDGER_WRITES_PER_CALLER = 300

# Groups one account can create in a window. Nobody legitimately creates 25
# groups a day.
MAX_GROUPS_PER_CALLER = 25


def window_cutoff(db: AsyncSession, window: timedelta = WRITE_WINDOW) -> datetime:
    """Start of a rate-limit window, in the flavour the bound dialect stores
    `created_at` as. Postgres keeps TIMESTAMPTZ; SQLite (tests) keeps the
    naive UTC text CURRENT_TIMESTAMP produces, and comparing that against an
    offset-aware bind parameter compares wrong."""
    cutoff = datetime.now(timezone.utc) - window
    if db.get_bind().dialect.name == "sqlite":
        return cutoff.replace(tzinfo=None)
    return cutoff


def _too_many(detail: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=detail,
        headers={"Retry-After": str(int(WRITE_WINDOW.total_seconds()))},
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


async def record_write(db: AsyncSession, caller: uuid.UUID, kind: str) -> None:
    """Charge one slot to the caller.

    Call it in the same transaction as the row it authorizes, so the two commit
    or roll back together. The event is added to the session rather than
    committed here — the endpoint owns the transaction.
    """
    # Opportunistic prune, scoped to this caller: rows that have aged out of
    # the window can never be counted again, and a serverless function has
    # nowhere to hang a cron. Usually deletes nothing, and the
    # (user_id, created_at) index makes finding that out cheap. Done before the
    # insert below so it can never sweep the row being written.
    await db.execute(
        delete(WriteEvent).where(
            WriteEvent.user_id == caller,
            WriteEvent.created_at < window_cutoff(db),
        )
    )
    db.add(WriteEvent(user_id=caller, kind=kind))


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
