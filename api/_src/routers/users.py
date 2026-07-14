import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..balances import net_balances
from ..db import get_db
from ..deps import DELETED_EMAIL_SUFFIX, get_active_user
from ..models import Group, GroupMember

router = APIRouter(prefix="/users", tags=["users"])

# NOTE: GET /users/search was removed on security review — it let any
# authenticated caller probe whether an email is registered and fetch the
# name/avatar. The invitation flow covers the lookup use case with a smaller
# surface (membership required, an invitation record is created).


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Delete the caller's account.

    Refuses while the caller has a non-zero balance in any currency of any
    group. Ledger history (expenses/settlements they took part in) is kept
    for the other members, so the public.users row is anonymized rather than
    deleted; the auth.users row is removed, which revokes all sign-in.
    """
    user = await get_active_user(db, caller)

    group_ids = sorted(
        (
            await db.execute(
                select(GroupMember.group_id).where(GroupMember.user_id == caller)
            )
        ).scalars().all()
    )
    if group_ids:
        # Exclusive locks on every group, in deterministic (sorted) order to
        # avoid deadlocks: no expense/settlement write (shared lock) can slip
        # in between the zero-balance checks below and the membership removal.
        await db.execute(
            select(Group.id)
            .where(Group.id.in_(group_ids))
            .order_by(Group.id)
            .with_for_update()
        )
    unsettled: set[str] = set()
    for group_id in group_ids:
        buckets = await net_balances(db, group_id)
        unsettled.update(
            c for c, users in buckets.items() if users.get(caller, 0) != 0
        )
    if unsettled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete account with outstanding balances in: "
                + ", ".join(sorted(unsettled))
            ),
        )

    # Single transaction: leave groups, anonymize PII, revoke sign-in.
    await db.execute(delete(GroupMember).where(GroupMember.user_id == caller))
    user.email = f"deleted-{caller}{DELETED_EMAIL_SUFFIX}"
    user.full_name = "Deleted user"
    user.avatar_url = None
    await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": str(caller)})
    await db.commit()
