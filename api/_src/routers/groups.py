import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..balances import greedy_simplify, net_balances
from ..db import get_db
from ..deps import require_membership
from ..models import Group, GroupMember, User
from ..schemas import (
    BalanceTransfer,
    GroupCreate,
    GroupDetailOut,
    GroupOut,
    MemberAdd,
    UserOut,
)

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    groups = (
        await db.execute(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == caller)
            .order_by(Group.created_at.desc())
        )
    ).scalars().all()
    return groups


@router.post("", response_model=GroupOut, status_code=201)
async def create_group(
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    group = Group(name=body.name, created_by=caller)
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_id=caller))
    await db.commit()
    return group


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    group = await db.get(Group, group_id)
    members = (
        await db.execute(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.joined_at)
        )
    ).scalars().all()
    return GroupDetailOut(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        members=[UserOut.model_validate(m) for m in members],
    )


@router.post("/{group_id}/members", response_model=UserOut, status_code=201)
async def add_member(
    group_id: uuid.UUID,
    body: MemberAdd,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    user = await db.get(User, body.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    existing = await db.get(GroupMember, (group_id, body.user_id))
    if existing is not None:
        raise HTTPException(status_code=400, detail="User is already a member of this group")
    db.add(GroupMember(group_id=group_id, user_id=body.user_id))
    await db.commit()
    return user


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    member = await db.get(GroupMember, (group_id, user_id))
    if member is None:
        raise HTTPException(status_code=404, detail="User is not a member of this group")
    # Strictly fail if the target user has a non-zero net balance in ANY
    # currency within this group (spec §4) — every bucket is checked.
    buckets = await net_balances(db, group_id)
    unsettled = [c for c, users in buckets.items() if users.get(user_id, 0) != 0]
    if unsettled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot remove member with outstanding balances in: "
                + ", ".join(sorted(unsettled))
            ),
        )
    await db.delete(member)
    await db.commit()


@router.get("/{group_id}/balances", response_model=dict[str, list[BalanceTransfer]])
async def get_balances(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    buckets = await net_balances(db, group_id)
    simplified = greedy_simplify(buckets)
    return {
        currency: [BalanceTransfer(**t) for t in transfers]
        for currency, transfers in simplified.items()
    }
