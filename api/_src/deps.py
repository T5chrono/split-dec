import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Expense, Group, GroupMember, Settlement


async def lock_group(db: AsyncSession, group_id: uuid.UUID, *, exclusive: bool) -> None:
    """Take a row lock on the group to serialize financial writes against a
    concurrent group deletion. Writers that add/increase obligations take a
    shared lock; delete_group takes an exclusive lock and re-checks balances
    while holding it, so nothing can slip in between the check and the deletes.
    (No-op on SQLite, which ignores row-level locking clauses.)"""
    await db.execute(
        select(Group.id).where(Group.id == group_id).with_for_update(read=not exclusive)
    )


async def require_membership(
    db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """404 if the group doesn't exist, 403 if the caller isn't a member."""
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    member = await db.get(GroupMember, (group_id, user_id))
    if member is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")


async def get_expense_for_member(
    db: AsyncSession, expense_id: uuid.UUID, user_id: uuid.UUID
) -> Expense:
    expense = (
        await db.execute(
            select(Expense).where(Expense.id == expense_id, Expense.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    await require_membership(db, expense.group_id, user_id)
    return expense


async def get_settlement_for_member(
    db: AsyncSession, settlement_id: uuid.UUID, user_id: uuid.UUID
) -> Settlement:
    settlement = (
        await db.execute(
            select(Settlement).where(
                Settlement.id == settlement_id, Settlement.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if settlement is None:
        raise HTTPException(status_code=404, detail="Settlement not found")
    await require_membership(db, settlement.group_id, user_id)
    return settlement
