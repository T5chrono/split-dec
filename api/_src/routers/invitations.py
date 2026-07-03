import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..db import get_db
from ..deps import require_membership
from ..emailer import send_invitation_email
from ..models import Group, GroupInvitation, GroupMember, User
from ..schemas import (
    InvitationCreate,
    InvitationCreatedOut,
    InvitationOut,
    MyInvitationOut,
)

router = APIRouter(tags=["invitations"])


async def _get_pending_for_invitee(
    db: AsyncSession, invitation_id: uuid.UUID, caller: uuid.UUID
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
    me = await db.get(User, caller)
    if invitation.invited_user_id != caller and (
        me is None or invitation.email != me.email.lower()
    ):
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
    await require_membership(db, group_id, caller)
    email = body.email.lower()

    invitee = (
        await db.execute(select(User).where(func.lower(User.email) == email))
    ).scalar_one_or_none()
    if invitee is not None:
        member = await db.get(GroupMember, (group_id, invitee.id))
        if member is not None:
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
        response.status_code = 200
        return InvitationCreatedOut(
            **InvitationOut.model_validate(existing).model_dump(),
            user_exists=invitee is not None,
            email_sent=False,
        )

    invitation = GroupInvitation(
        group_id=group_id,
        email=email,
        invited_by=caller,
        invited_user_id=invitee.id if invitee else None,
    )
    db.add(invitation)
    await db.commit()

    email_sent = False
    if invitee is None:
        # Not on SplitDec yet: try to email them (best-effort; the frontend
        # offers a mailto draft when this comes back False).
        inviter = await db.get(User, caller)
        group = await db.get(Group, group_id)
        email_sent = await send_invitation_email(
            email, inviter.full_name or inviter.email, group.name
        )

    return InvitationCreatedOut(
        **InvitationOut.model_validate(invitation).model_dump(),
        user_exists=invitee is not None,
        email_sent=email_sent,
    )


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
    await db.delete(invitation)
    await db.commit()


@router.get("/invitations/mine", response_model=list[MyInvitationOut])
async def my_invitations(
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    me = await db.get(User, caller)
    if me is None:
        return []
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
    invitation = await _get_pending_for_invitee(db, invitation_id, caller)
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
