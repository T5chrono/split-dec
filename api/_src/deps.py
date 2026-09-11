import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Integer, Select, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .balances import net_balances
from .models import Expense, Group, GroupInvitation, GroupMember, Settlement, User

# Anonymized users keep their public.users row for ledger history but must
# never act again (their auth.users row is gone, yet a JWT issued before
# deletion stays cryptographically valid until it expires).
DELETED_EMAIL_SUFFIX = "@users.splitdec.invalid"


# Row locks on the *user* serialize account deletion against the endpoints
# that hand the caller a new membership. Deletion snapshots the caller's
# groups, checks their balances and then removes the memberships; without
# this, a group creation or invitation acceptance committing in between
# leaves the deleted account a member of a group — and membership-gated
# routes don't re-check liveness, so an unexpired JWT would keep working.
#
# "exclusive" is FOR NO KEY UPDATE, not FOR UPDATE, on purpose: FOR UPDATE
# conflicts with the FOR KEY SHARE that Postgres takes on users rows for
# every FK insert (expense_splits, settlements, ...). A concurrent expense
# write already holds the group's shared lock while doing those inserts, so
# FOR UPDATE here would deadlock against the group-lock protocol. FOR NO KEY
# UPDATE still conflicts with the FOR SHARE taken below, which is all the
# mutual exclusion this needs.
UserLock = Literal["shared", "exclusive"] | None


async def get_active_user(
    db: AsyncSession, user_id: uuid.UUID, *, lock: UserLock = None
) -> User:
    """401 for callers whose account no longer exists or has been deleted.

    Used by endpoints not already gated by group membership (membership rows
    are removed on account deletion, so membership-guarded routes are safe).

    Pass `lock="shared"` before creating a membership and `lock="exclusive"`
    in account deletion: the liveness check is then re-read under the lock,
    so a membership either lands before the snapshot or is refused with 401.
    """
    if lock is None:
        user = await db.get(User, user_id)
    else:
        user = (
            await db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update(read=(lock == "shared"), key_share=(lock == "exclusive"))
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
    if user is None or user.email.endswith(DELETED_EMAIL_SUFFIX):
        raise HTTPException(status_code=401, detail="Account is no longer active")
    return user

# Row locks on the group serialize financial writes against a concurrent
# group deletion: writers that add/increase obligations take a shared lock,
# delete_group takes an exclusive one and re-checks balances while holding
# it. Locks ride along the authorization query (no extra round trip) and are
# ignored by SQLite in tests. Postgres allows FOR SHARE/UPDATE only OF the
# non-nullable side of an outer join, which Group is in all queries below.
GroupLock = Literal["shared", "exclusive"] | None


def _with_group_lock(stmt: Select, lock: GroupLock) -> Select:
    if lock is None:
        return stmt
    return stmt.with_for_update(read=(lock == "shared"), of=Group)


async def lock_groups_exclusive(db: AsyncSession, group_ids: list[uuid.UUID]) -> None:
    """Exclusive locks on multiple groups at once, in deterministic (sorted)
    order so concurrent multi-group lockers cannot deadlock each other. Used
    by account deletion before its per-group zero-balance checks. (No-op on
    SQLite, which ignores row-level locking clauses.)"""
    if not group_ids:
        return
    await db.execute(
        select(Group.id)
        .where(Group.id.in_(group_ids))
        .order_by(Group.id)
        .with_for_update()
    )


# How many people one group holds. A **seat** is a member or a PENDING
# invitation, so a group can never issue more invitations than it has room for
# and the refusal lands on the inviter rather than on the invitee at the moment
# they accept.
#
# The number is a product decision rather than a technical threshold: 100 is far
# above any real use of a bill splitter, and the screens are what it protects —
# the members tab and the split editor render one unvirtualised row per member,
# and because splits may only name current members (routers/expenses.py) a cap
# on the group is automatically a cap on the rows one expense writes.
#
# Easier to raise than to lower: lowering it strands groups already over the
# line, which nothing here refuses retroactively.
MAX_GROUP_MEMBERS = 100

# Advisory-lock namespace for the seat count. Must not collide with
# ratelimit._LOCK_SPACE, which owns 1-4 for the write windows.
_SEAT_LOCK_SPACE = 5


async def hold_group_seats(db: AsyncSession, group_id: uuid.UUID) -> None:
    """Serialize one group's count-the-seats-then-take-one until this
    transaction ends.

    Counting and inserting are two statements, so without this N concurrent
    joins all count the same N-1 seats and all succeed. Same rule the write
    quotas follow (ratelimit._hold_window), and the mechanics are the same:

    `pg_advisory_xact_lock`, never the session-scoped variant — the connection
    goes back to the transaction pooler at commit (db.py) and a session lock
    would ride into the next borrower's transaction with nobody left to release
    it. Both operands are cast explicitly because Postgres has a (bigint) form
    and an (int4, int4) form and no (bigint, bigint) one, so leaving the types
    to inference is a resolution failure waiting for a driver change. The low 4
    bytes of the uuid are as good as any hash: a collision costs two unrelated
    groups a brief wait.

    Deliberately an advisory lock rather than FOR UPDATE on the group row. The
    row lock is the ledger's (see the GroupLock protocol above) — taking the
    exclusive one here would make joining a group queue behind every expense
    write on it, and make every expense write wait out a join, for a count that
    has nothing to do with money. This one conflicts with exactly the other
    thing that takes a seat.

    A no-op outside Postgres: SQLite (tests) runs one connection at a time and
    has nothing to serialize.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    key = int.from_bytes(group_id.bytes[:4], "big", signed=True)
    await db.execute(
        select(
            func.pg_advisory_xact_lock(
                cast(_SEAT_LOCK_SPACE, Integer), cast(key, Integer)
            )
        )
    )


async def ensure_group_has_room(
    db: AsyncSession, group_id: uuid.UUID, *, counting_invitations: bool
) -> None:
    """Refuse to fill a seat in a group that has none left.

    `counting_invitations` is the difference between the two callers.
    Inviting counts members *and* pending invitations, because the invitation it
    is about to create reserves a seat. Accepting counts members only: the
    invitation being answered is already holding one, and accepting converts it
    rather than adding another.

    Callers must hold `hold_group_seats` for the same group, or this counts a
    number that another request is already invalidating.
    """
    members = (
        select(func.count())
        .select_from(GroupMember)
        .where(GroupMember.group_id == group_id)
        .scalar_subquery()
    )
    pending = (
        select(func.count())
        .select_from(GroupInvitation)
        .where(
            GroupInvitation.group_id == group_id,
            GroupInvitation.status == "PENDING",
        )
        .scalar_subquery()
    )
    taken = (
        await db.execute(select(members + pending if counting_invitations else members))
    ).scalar_one()
    if taken >= MAX_GROUP_MEMBERS:
        raise HTTPException(
            status_code=400,
            detail=f"This group is full ({MAX_GROUP_MEMBERS} people is the limit).",
        )


def raise_unless_member(*, group_exists: bool, is_member: bool) -> None:
    """The single authorization decision for group access: 404 for a missing
    group, 403 for a non-member. Every code path that answers "may this
    caller touch this group?" must funnel through here (FastAPI is the sole
    authz boundary — RLS is off)."""
    if not group_exists:
        raise HTTPException(status_code=404, detail="Group not found")
    if not is_member:
        raise HTTPException(status_code=403, detail="You are not a member of this group")


async def require_membership(
    db: AsyncSession,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    lock: GroupLock = None,
) -> None:
    """404 if the group doesn't exist, 403 if the caller isn't a member.

    Single round trip: group existence and the caller's membership come back
    in one row via an outer join.
    """
    stmt = (
        select(Group.id, GroupMember.user_id)
        .outerjoin(
            GroupMember,
            (GroupMember.group_id == Group.id) & (GroupMember.user_id == user_id),
        )
        .where(Group.id == group_id)
    )
    row = (await db.execute(_with_group_lock(stmt, lock))).first()
    raise_unless_member(group_exists=row is not None, is_member=row is not None and row.user_id is not None)


async def ensure_no_outsider_debt(db: AsyncSession, group_id: uuid.UUID) -> None:
    """Refuse a ledger change that leaves a non-member owing or owed.

    A member can only be removed while their balance is zero
    (routers/groups.py), but nothing kept it there afterwards. Soft-deleting an
    expense that former member had paid for — or rewriting its splits without
    them — moves their net off zero, and they have no way back in to settle it:
    they are not a member, so they cannot be a party to a settlement. The group
    inherits the debt permanently, and can never be deleted either, since that
    demands every balance be zero too. One delete could strand a group forever.

    Call it after the mutation has been flushed, so the balances read here are
    the ones about to be committed. The lock this endpoint already holds on the
    group (shared) is what stops a concurrent removal from invalidating the
    answer: remove_member takes the exclusive one.

    A group already in that state — the damage predates this check — is
    recoverable rather than bricked: invite the person back, and their balance
    is theirs to settle again, with remove_member re-checking it is zero on the
    way out.
    """
    buckets = await net_balances(db, group_id)
    if not buckets:
        return
    members = set(
        (
            await db.execute(
                select(GroupMember.user_id).where(GroupMember.group_id == group_id)
            )
        ).scalars().all()
    )
    stranded = sorted(
        {c for c, users in buckets.items() if not users.keys() <= members}
    )
    if stranded:
        raise HTTPException(
            status_code=400,
            detail=(
                "This change would leave someone who is no longer in the group "
                "with an unsettled balance in: " + ", ".join(stranded)
            ),
        )


def record_edit(row, caller: uuid.UUID) -> None:
    """Stamp who last changed a ledger row, and when.

    Every mutation that actually changes something goes through here — the
    metadata-only PATCH, the full splits rewrite, and the soft-delete, which is
    the most disputable of the three and the one it would be easiest to leave
    out. **Whether a request changed anything is the caller's judgement, not
    this function's**: both update endpoints compare against the stored row
    first, because a PATCH that resubmits what is already there is not an edit,
    and "edited by Bob" because Bob opened the form and pressed Save is a false
    positive on the one signal the record exists to give. A delete always
    qualifies. `updated_by` is stored
    whoever the caller is, including the row's own author; whether that is
    *shown* is decided in the UI (ExpensesTab surfaces it only when it differs
    from `created_by`), because what belongs on the record and what belongs on
    screen are not the same question.

    The clock is ours rather than the database's: a server default would need
    an ON UPDATE trigger to fire on edits, and this codebase keeps its triggers
    to the two on `auth.users` that it cannot avoid.
    """
    row.updated_by = caller
    row.updated_at = datetime.now(timezone.utc)


async def get_expense_for_member(
    db: AsyncSession,
    expense_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    lock: GroupLock = None,
) -> Expense:
    """Fetch the expense and verify the caller's membership in one query."""
    stmt = (
        select(Expense, GroupMember.user_id)
        .join(Group, Group.id == Expense.group_id)
        .outerjoin(
            GroupMember,
            (GroupMember.group_id == Expense.group_id)
            & (GroupMember.user_id == user_id),
        )
        .where(Expense.id == expense_id, Expense.deleted_at.is_(None))
    )
    row = (await db.execute(_with_group_lock(stmt, lock))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    expense, member_id = row
    raise_unless_member(group_exists=True, is_member=member_id is not None)
    return expense


async def get_settlement_for_member(
    db: AsyncSession,
    settlement_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    lock: GroupLock = None,
) -> Settlement:
    """Fetch the settlement and verify the caller's membership in one query."""
    stmt = (
        select(Settlement, GroupMember.user_id)
        .join(Group, Group.id == Settlement.group_id)
        .outerjoin(
            GroupMember,
            (GroupMember.group_id == Settlement.group_id)
            & (GroupMember.user_id == user_id),
        )
        .where(Settlement.id == settlement_id, Settlement.deleted_at.is_(None))
    )
    row = (await db.execute(_with_group_lock(stmt, lock))).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    settlement, member_id = row
    raise_unless_member(group_exists=True, is_member=member_id is not None)
    return settlement
