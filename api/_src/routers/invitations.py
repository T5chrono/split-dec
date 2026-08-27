import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..db import get_db
from ..deps import get_active_user, require_membership
from ..emailer import send_invitation_email
from ..models import Group, GroupInvitation, GroupMember, User
from ..ratelimit import INVITE, enforce_invitation_quota, record_write
from ..schemas import (
    InvitationCreate,
    InvitationCreatedOut,
    InvitationOut,
    MyInvitationOut,
)

router = APIRouter(tags=["invitations"])


async def _get_pending_for_invitee(
    db: AsyncSession, invitation_id: uuid.UUID, caller: uuid.UUID, *, lock_user: bool = False
) -> GroupInvitation:
    """Authorization only: the caller may answer this invitation, as of now.

    Deliberately an unlocked read. Whether the invitation is *still* pending
    when the answer lands is decided by `_resolve_invitation`, which puts the
    predicate in the UPDATE rather than trusting what this saw.
    """
    invitation = (
        await db.execute(
            select(GroupInvitation).where(
                GroupInvitation.id == invitation_id,
                GroupInvitation.status == "PENDING",
            )
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    # Deleted accounts must not respond. Accepting also creates a membership,
    # so that path holds the shared user lock against account deletion.
    me = await get_active_user(db, caller, lock="shared" if lock_user else None)
    if invitation.invited_user_id != caller and invitation.email != me.email.lower():
        raise HTTPException(status_code=403, detail="This invitation is not addressed to you")
    return invitation


async def _resolve_invitation(
    db: AsyncSession,
    invitation_id: uuid.UUID,
    *,
    status: str,
    invited_user_id: uuid.UUID | None = None,
) -> bool:
    """Move a PENDING invitation to a final status. Returns whether this call
    is the one that moved it.

    `status = 'PENDING'` belongs in the UPDATE itself, not only in the read
    that preceded it. Accept, decline and cancel all read the row and then
    write a different status, and a read that is not part of its own write can
    be stale by the time the write lands: two of them would both see PENDING,
    both succeed, and a cancelled invitation would still have granted
    membership. Postgres re-evaluates this predicate after waiting out
    whoever holds the row, so exactly one concurrent answer updates a row and
    every other sees rowcount 0 — no row lock held across the caller's
    decision, and nothing for the group-lock protocol (deps.py) to deadlock
    against.
    """
    values: dict = {"status": status, "responded_at": datetime.now(timezone.utc)}
    if invited_user_id is not None:
        values["invited_user_id"] = invited_user_id
    result = await db.execute(
        update(GroupInvitation)
        .where(
            GroupInvitation.id == invitation_id,
            GroupInvitation.status == "PENDING",
        )
        .values(**values)
    )
    return result.rowcount == 1


def _already_answered() -> HTTPException:
    """Lost the race for an invitation that was PENDING a moment ago. 404, the
    same answer the loser would have got had it arrived a moment later — the
    invitation no longer exists as something to answer."""
    return HTTPException(status_code=404, detail="Invitation not found")


@router.post(
    "/groups/{group_id}/invitations",
    response_model=InvitationCreatedOut,
    status_code=201,
)
async def invite_to_group(
    group_id: uuid.UUID,
    body: InvitationCreate,
    response: Response,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Invite an email address to the group.

    The response is deliberately uniform: it never says whether the address
    belongs to a registered account, and the endpoint behaves the same either
    way (same email attempt, same latency, same stored row). Any member can
    create a group and invite arbitrary addresses, so a response that varied
    would be an account-registration oracle open to anyone — the same reason
    GET /users/search was removed (see users.py).
    """
    await require_membership(db, group_id, caller)
    email = body.email.lower()

    # Whether the address is registered, and whether it is already in this
    # group, in one round trip — so the registered and unregistered paths
    # don't even differ by a query.
    row = (
        await db.execute(
            select(User.id, GroupMember.user_id.label("member_id"))
            .outerjoin(
                GroupMember,
                (GroupMember.user_id == User.id) & (GroupMember.group_id == group_id),
            )
            .where(func.lower(User.email) == email)
        )
    ).first()
    invitee_id = row.id if row is not None else None
    if row is not None and row.member_id is not None:
        # Not a leak: the caller is a member and can already list members.
        raise HTTPException(status_code=400, detail="User is already a member of this group")

    existing = (
        await db.execute(
            select(GroupInvitation).where(
                GroupInvitation.group_id == group_id,
                GroupInvitation.email == email,
                GroupInvitation.status == "PENDING",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        # Replay: no new row, no second email, no quota consumed.
        response.status_code = 200
        return InvitationCreatedOut.model_validate(existing)

    await enforce_invitation_quota(db, caller, email)
    # Charged to the inviter and keyed to a digest of the recipient, in a table
    # that outlives this group — deleting the group used to hand all three
    # windows back. Committed with the invitation below, so the duplicate race
    # rolls it back with everything else.
    await record_write(db, caller, INVITE, recipient=email)

    # Load everything the post-commit email needs BEFORE committing, so the
    # (up to 10s) provider call never holds a checked-out pooler connection
    # inside a fresh implicit transaction.
    inviter = await db.get(User, caller)
    group = await db.get(Group, group_id)
    inviter_name = inviter.full_name or inviter.email
    group_name = group.name

    invitation = GroupInvitation(
        group_id=group_id,
        email=email,
        invited_by=caller,
        invited_user_id=invitee_id,
    )
    db.add(invitation)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent duplicate (double-click/retry) hit the partial unique
        # index; return the winner idempotently, like expense creation does.
        await db.rollback()
        existing = (
            await db.execute(
                select(GroupInvitation).where(
                    GroupInvitation.group_id == group_id,
                    GroupInvitation.email == email,
                    GroupInvitation.status == "PENDING",
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(status_code=400, detail="Invitation could not be created")
        response.status_code = 200
        return InvitationCreatedOut.model_validate(existing)

    # Emailed whether or not the address is registered: registered invitees
    # get a nudge, and unregistered ones cannot be distinguished by the
    # caller through latency or a missing side effect. Best-effort — the
    # session's transaction is closed here, so no connection is held.
    await send_invitation_email(
        email, inviter_name, group_name, correlator=invitation.id
    )

    return InvitationCreatedOut.model_validate(invitation)


@router.get("/groups/{group_id}/invitations", response_model=list[InvitationOut])
async def list_group_invitations(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    return (
        await db.execute(
            select(GroupInvitation)
            .where(
                GroupInvitation.group_id == group_id,
                GroupInvitation.status == "PENDING",
            )
            .order_by(GroupInvitation.created_at)
        )
    ).scalars().all()


@router.delete("/invitations/{invitation_id}", status_code=204)
async def cancel_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    invitation = (
        await db.execute(
            select(GroupInvitation).where(
                GroupInvitation.id == invitation_id,
                GroupInvitation.status == "PENDING",
            )
        )
    ).scalar_one_or_none()
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    await require_membership(db, invitation.group_id, caller)
    # Marked, not deleted: the row is this group's record that the invitation
    # happened. The send quotas no longer depend on that — they count
    # write_events, which a delete here would not touch either way — but the
    # partial unique index only covers PENDING rows, so re-inviting still works.
    # Conditional on it still being PENDING, so cancelling never overwrites an
    # answer that landed while the caller was deciding.
    if not await _resolve_invitation(db, invitation_id, status="CANCELLED"):
        raise _already_answered()
    await db.commit()


@router.get("/invitations/mine", response_model=list[MyInvitationOut])
async def my_invitations(
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    me = await get_active_user(db, caller)  # deleted accounts see nothing
    rows = (
        await db.execute(
            select(GroupInvitation, Group.name, User.full_name)
            .join(Group, Group.id == GroupInvitation.group_id)
            .join(User, User.id == GroupInvitation.invited_by)
            .where(
                GroupInvitation.status == "PENDING",
                (GroupInvitation.invited_user_id == caller)
                | (GroupInvitation.email == me.email.lower()),
            )
            .order_by(GroupInvitation.created_at.desc())
        )
    ).all()
    return [
        MyInvitationOut(
            id=inv.id,
            group_id=inv.group_id,
            group_name=group_name,
            invited_by_name=inviter_name,
            created_at=inv.created_at,
        )
        for inv, group_name, inviter_name in rows
    ]


@router.post("/invitations/{invitation_id}/accept", status_code=204)
async def accept_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    invitation = await _get_pending_for_invitee(db, invitation_id, caller, lock_user=True)
    if await db.get(GroupMember, (invitation.group_id, caller)) is None:
        db.add(GroupMember(group_id=invitation.group_id, user_id=caller))
        # Flushed before the invitation is touched, so this transaction takes
        # the group's row (an FK insert takes FOR KEY SHARE on it) and then the
        # invitation's — the order delete_group takes them in. The reverse
        # order is the one that deadlocks.
        await db.flush()
    if not await _resolve_invitation(
        db, invitation_id, status="ACCEPTED", invited_user_id=caller
    ):
        # Cancelled or answered elsewhere between the read above and here. The
        # membership goes with the rollback — accepting is one decision.
        await db.rollback()
        raise _already_answered()
    await db.commit()


@router.post("/invitations/{invitation_id}/decline", status_code=204)
async def decline_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await _get_pending_for_invitee(db, invitation_id, caller)
    if not await _resolve_invitation(
        db, invitation_id, status="DECLINED", invited_user_id=caller
    ):
        raise _already_answered()
    await db.commit()
