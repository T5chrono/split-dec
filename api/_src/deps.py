import uuid
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Expense, Group, GroupMember, Settlement

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
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found")
    if row.user_id is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")


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
    if member_id is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
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
    if member_id is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")
    return settlement
