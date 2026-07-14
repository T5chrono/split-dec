import uuid
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Expense, Group, GroupMember, Settlement, User

# Anonymized users keep their public.users row for ledger history but must
# never act again (their auth.users row is gone, yet a JWT issued before
# deletion stays cryptographically valid until it expires).
DELETED_EMAIL_SUFFIX = "@users.splitdec.invalid"


async def get_active_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    """401 for callers whose account no longer exists or has been deleted.

    Used by endpoints not already gated by group membership (membership rows
    are removed on account deletion, so membership-guarded routes are safe)."""
    user = await db.get(User, user_id)
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
