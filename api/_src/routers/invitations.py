import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..db import get_db
from ..deps import get_active_user, require_membership
from ..emailer import send_invitation_email
from ..models import Group, GroupInvitation, GroupMember, User
from ..schemas import (
    InvitationCreate,
    InvitationCreatedOut,
    InvitationOut,
    MyInvitationOut,
)

router = APIRouter(tags=["invitations"])

# Every invitation to a non-member triggers an outbound email, and cancelling
# one frees its (group, email) slot immediately — so without quotas a single
# account can drive an unbounded invite/cancel loop at any address and burn
# the sending domain's reputation. Cancelled invitations are kept (status
# CANCELLED) precisely so they still count against these windows.
INVITE_WINDOW = timedelta(hours=24)
INVITE_MAX_PER_INVITER = 20  # one person inviting, across all their groups
INVITE_MAX_PER_RECIPIENT = 3  # one address, however many accounts aim at it
INVITE_MAX_GLOBAL = 300  # whole-deployment brake on a compromised account


def _window_cutoff(db: AsyncSession) -> datetime:
    """Start of the rate-limit window, in the flavour the bound dialect
    stores `created_at` as. Postgres keeps TIMESTAMPTZ; SQLite (tests) keeps
    the naive UTC text CURRENT_TIMESTAMP produces, and comparing that against
    an offset-aware bind parameter compares wrong."""
    cutoff = datetime.now(timezone.utc) - INVITE_WINDOW
    if db.get_bind().dialect.name == "sqlite":
        return cutoff.replace(tzinfo=None)
    return cutoff


async def _enforce_invite_quota(db: AsyncSession, caller: uuid.UUID, email: str) -> None:
    """429 once any of the three windows is exhausted. One round trip."""
    by_caller, by_recipient, overall = (
        await db.execute(
            select(
                func.sum(case((GroupInvitation.invited_by == caller, 1), else_=0)),
                func.sum(case((GroupInvitation.email == email, 1), else_=0)),
                func.count(),
            ).where(GroupInvitation.created_at >= _window_cutoff(db))
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
        raise HTTPException(
            status_code=429,
            detail="Too many invitations sent recently. Please try again later.",
            headers={"Retry-After": str(int(INVITE_WINDOW.total_seconds()))},
        )


async def _get_pending_for_invitee(
    db: AsyncSession, invitation_id: uuid.UUID, caller: uuid.UUID, *, lock_user: bool = False
) -> GroupInvitation:
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

    await _enforce_invite_quota(db, caller, email)

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
    # Marked, not deleted: a deleted row would let an invite/cancel loop
    # reset the send quotas in _enforce_invite_quota. The partial unique
    # index only covers PENDING rows, so re-inviting still works.
    invitation.status = "CANCELLED"
    invitation.responded_at = datetime.now(timezone.utc)
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
    invitation.status = "ACCEPTED"
    invitation.invited_user_id = caller
    invitation.responded_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/invitations/{invitation_id}/decline", status_code=204)
async def decline_invitation(
    invitation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    invitation = await _get_pending_for_invitee(db, invitation_id, caller)
    invitation.status = "DECLINED"
    invitation.invited_user_id = caller
    invitation.responded_at = datetime.now(timezone.utc)
    await db.commit()
