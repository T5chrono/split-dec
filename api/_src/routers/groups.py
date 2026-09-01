import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..balances import expense_totals, greedy_simplify, net_balances
from ..db import get_db
from ..deps import get_active_user, raise_unless_member, require_membership
from ..models import (
    Expense,
    ExpenseSplit,
    Group,
    GroupInvitation,
    GroupMember,
    Settlement,
    User,
)
from ..ratelimit import GROUP, enforce_group_creation_quota, record_write
from ..schemas import (
    BalanceTransfer,
    CurrencyTotalOut,
    GroupCreate,
    GroupDetailOut,
    GroupOut,
    UserOut,
)

router = APIRouter(prefix="/groups", tags=["groups"])


async def purge_group(db: AsyncSession, group: Group) -> None:
    """Delete a group and all its records, without committing.

    Children go explicitly: Postgres also has ON DELETE CASCADE, but the ORM
    FKs don't declare it and SQLite tests don't cascade. Callers must already
    hold the group's exclusive lock, and own the transaction.
    """
    expense_ids = select(Expense.id).where(Expense.group_id == group.id)
    await db.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id.in_(expense_ids)))
    await db.execute(delete(Expense).where(Expense.group_id == group.id))
    await db.execute(delete(Settlement).where(Settlement.group_id == group.id))
    await db.execute(delete(GroupInvitation).where(GroupInvitation.group_id == group.id))
    await db.execute(delete(GroupMember).where(GroupMember.group_id == group.id))
    await db.delete(group)


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
    # Not membership-gated, so explicitly refuse tokens of deleted accounts.
    # The shared lock holds until commit, so a concurrent account deletion
    # cannot snapshot this caller's groups before the membership below exists.
    await get_active_user(db, caller, lock="shared")
    await enforce_group_creation_quota(db, caller)
    # Outlives the group: deleting one must not hand back the slot it cost.
    await record_write(db, caller, GROUP)
    group = Group(name=body.name, created_by=caller)
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_id=caller))
    await db.commit()
    return group


@router.patch("/{group_id}", response_model=GroupOut)
async def rename_group(
    group_id: uuid.UUID,
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    # Shared lock like the other group-mutating endpoints: serializes against
    # a concurrent delete_group so the follow-up get can't find nothing.
    await require_membership(db, group_id, caller, lock="shared")
    group = await db.get(Group, group_id)
    group.name = body.name
    await db.commit()
    return group


@router.get("/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    # Group, members, and the caller's membership in one round trip.
    rows = (
        await db.execute(
            select(Group, User)
            .outerjoin(GroupMember, GroupMember.group_id == Group.id)
            .outerjoin(User, User.id == GroupMember.user_id)
            .where(Group.id == group_id)
            .order_by(GroupMember.joined_at)
        )
    ).all()
    members = [u for _, u in rows if u is not None]
    raise_unless_member(
        group_exists=bool(rows),
        is_member=caller in {m.id for m in members},
    )
    group = rows[0][0]
    return GroupDetailOut(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        members=[UserOut.model_validate(m) for m in members],
    )


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Delete a group and all its records (members, expenses, splits,
    settlements, invitations cascade). Any member may delete, but only once
    the group is fully settled — no non-zero balance in any currency."""
    # The exclusive lock rides on the membership query: no expense/settlement
    # can be created/updated (they take a shared lock) between the
    # settled-check below and the deletes.
    await require_membership(db, group_id, caller, lock="exclusive")
    buckets = await net_balances(db, group_id)
    unsettled = sorted(c for c, users in buckets.items() if any(v != 0 for v in users.values()))
    if unsettled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete a group with outstanding balances in: "
                + ", ".join(unsettled)
            ),
        )
    await purge_group(db, await db.get(Group, group_id))
    await db.commit()


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    # Exclusive lock, like delete_group: the zero-balance check below must
    # not race a concurrent expense/settlement write (those take the shared
    # lock), or a member could leave carrying fresh obligations.
    await require_membership(db, group_id, caller, lock="exclusive")
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
    # A group with no members is unreachable: every route into it is
    # membership-gated, so nobody could ever read it, settle it or delete it,
    # and its rows would outlive everyone who could account for them. Refused
    # rather than silently purged — deleting the group is the same gesture, one
    # screen away (GroupSettingsModal), behind its own confirmation. Checked
    # after the balances, so the message the caller gets is the one they can
    # act on: an unsettled group says so, and a settled one is genuinely
    # deletable.
    remaining = (
        await db.execute(
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.user_id != user_id)
        )
    ).scalar_one()
    if remaining == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "This is the group's last member. Delete the group instead of "
                "leaving it empty."
            ),
        )
    # Pending invitations to this group addressed to the departing member are
    # revoked with the membership. An invitation is an unexpiring capability
    # that recreates membership on accept (invitations.accept_invitation), and
    # nothing else expires it, so one left behind lets the removed member walk
    # back in without any current member acting. delete_account already treats
    # them this way for the same reason (routers/users.py).
    #
    # Reachable because a person can hold more than one live invitation to a
    # group: uq_group_invitations_pending is keyed on (group_id, email), so a
    # changed address (handle_user_updated, migration 20260827000100) leaves the
    # invitation sent to the old one PENDING while they join through the new.
    # Matched on both columns, exactly as delete_account does — an invitation
    # created before the invitee had an account carries a NULL invited_user_id
    # and is only findable by address.
    #
    # Safe under the group-lock protocol (deps.py): the FOR UPDATE taken above
    # conflicts with the FOR KEY SHARE that accept_invitation's membership
    # insert takes on the group row, so a concurrent accept either commits
    # first (and is then removed like any other member) or blocks here and
    # loses on _resolve_invitation's `status = 'PENDING'` predicate. Group row
    # first, invitations second — the order delete_group takes, not the one
    # that deadlocks against it.
    #
    # CANCELLED rather than deleted, like cancel_invitation: the row is the
    # group's record that the invitation happened, and the partial unique index
    # covers only PENDING rows, so the member can still be re-invited.
    removed = await db.get(User, user_id)
    await db.execute(
        update(GroupInvitation)
        .where(
            GroupInvitation.group_id == group_id,
            GroupInvitation.status == "PENDING",
            (GroupInvitation.invited_user_id == user_id)
            | (func.lower(GroupInvitation.email) == removed.email.lower()),
        )
        .values(status="CANCELLED", responded_at=datetime.now(timezone.utc))
    )
    await db.delete(member)
    await db.commit()


@router.get("/{group_id}/totals", response_model=list[CurrencyTotalOut])
async def get_totals(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """How much the group has spent, one entry per currency used."""
    await require_membership(db, group_id, caller)
    totals = await expense_totals(db, group_id)
    return [
        CurrencyTotalOut(currency=currency, total=total)
        for currency, total in totals.items()
    ]


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
