import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..balances import net_balances
from ..db import get_db
from ..models import GroupMember, User
from ..schemas import UserSearchOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/search", response_model=UserSearchOut)
async def search_user(
    email: str = Query(min_length=3),
    db: AsyncSession = Depends(get_db),
    _caller: uuid.UUID = Depends(verify_jwt),
):
    user = (
        await db.execute(select(User).where(func.lower(User.email) == email.lower()))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="No user found with that email")
    return user


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
    user = await db.get(User, caller)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    group_ids = (
        await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == caller)
        )
    ).scalars().all()
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
    user.email = f"deleted-{caller}@users.splitdec.invalid"
    user.full_name = "Deleted user"
    user.avatar_url = None
    await db.execute(text("DELETE FROM auth.users WHERE id = :uid"), {"uid": str(caller)})
    await db.commit()
