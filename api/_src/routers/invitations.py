import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, func, or_, select, update
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
from ..unsubscribe import is_suppressed, mint_token

router = APIRouter(tags=["invitations"])


def invitee_predicate(caller: uuid.UUID, email: str):
    """Which invitations `caller` may answer. Exclusive, not an OR.

    An invitation carries `invited_user_id` from creation when the address
    already had an account, and acquires it on the answer otherwise. Once it
    is set, it is the *only* thing that authorizes: matching on the address as
    well lets whoever holds that mailbox next answer an invitation bound to
    somebody else. Addresses change hands — a user edits theirs
    (handle_user_updated) and the old one is free to register, a corporate
    address is reassigned — and nothing here expires, so the window is
    unbounded.

    Email matching stays for the case it exists for: an invitation sent to an
    address with no account yet, which is unbound until its invitee signs up
    and answers it.

    Note this is narrower than the predicate *revocation* uses
    (groups.remove_member, users.delete_account), which matches id OR address
    on purpose. Revoking a capability too widely is safe; granting one too
    widely is the bug above.
    """
    return or_(
        GroupInvitation.invited_user_id == caller,
        and_(
            GroupInvitation.invited_user_id.is_(None),
            GroupInvitation.email == email,
        ),
    )


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
    if invitation.invited_user_id is not None:
        authorized = invitation.invited_user_id == caller
    else:
        authorized = invitation.email == me.email.lower()
    if not authorized:
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
    # Shared lock, like every other write that depends on the caller still
    # being a member when it commits. Without it this endpoint read its
    # membership under no lock at all, so the caller's own account deletion --
    # which holds FOR UPDATE on each of their groups while it cancels the
    # invitations they issued (routers/users.py) -- could commit in between,
    # and this request would then land a PENDING invitation issued by an
    # account that no longer exists. That is the bug the cancellation sweep
    # exists to prevent, reintroduced through the back door. The lock makes the
    # two orderings the only two: commit first and be swept, or block and then
    # fail the membership check with 403.
    #
    # Group first, then the quota's advisory lock (enforce_invitation_quota) --
    # the same order create_expense takes, so the two cannot invert. Released
    # by the commit below, which is deliberately before the provider call, so
    # it never spans the email.
    await require_membership(db, group_id, caller, lock="shared")
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
    # Read here for the same reason as the two names above: the provider call
    # happens after the commit, and a read taken then would have checked a
    # pooler connection back out to hold across it.
    #
    # Note where this sits — *after* the quota was charged, not before. An
    # opt-out suppresses the email and nothing else: the row below is still
    # created, still visible in the app if this address ever signs up, and
    # still costs the sender a slot. Skipping the charge would let a caller
    # read their own remaining allowance to discover whether an address has
    # unsubscribed, which is the registration oracle this endpoint is built to
    # deny, rebuilt out of a rate limit.
    muted = await is_suppressed(db, email)

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
    #
    # Unless the address has opted out, which is the one thing that stops the
    # send. The caller is told nothing either way, and the invitation stands.
    if not muted:
        await send_invitation_email(
            email,
            inviter_name,
            group_name,
            correlator=invitation.id,
            unsubscribe_token=mint_token(email),
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
                invitee_predicate(caller, me.email.lower()),
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
        try:
            await db.flush()
        except IntegrityError:
            # Two shapes, one right answer. The group was deleted while this
            # request sat between the unlocked read above and here: the FK
            # insert waits on delete_group's FOR UPDATE and then finds no group
            # row (purge_group took the invitation with it). Or a concurrent
            # accept of the same invitation won and already inserted this
            # membership, violating the primary key. Either way the invitation
            # is gone as something to answer, which is what 404 says — an
            # unhandled IntegrityError here is a 500 instead.
            await db.rollback()
            raise _already_answered()
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
