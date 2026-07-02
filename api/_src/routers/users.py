import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..db import get_db
from ..models import User
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
