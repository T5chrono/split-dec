import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..currencies import precision_for
from ..db import get_db
from ..deps import get_settlement_for_member, require_membership
from ..models import GroupMember, Settlement
from ..schemas import SettlementCreate, SettlementOut, SettlementUpdate

router = APIRouter(tags=["settlements"])


def _validate_amount_precision(amount: Decimal, currency: str) -> None:
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > precision_for(currency):
        raise HTTPException(
            status_code=422,
            detail=f"Amount has more decimal places than {currency} allows",
        )


async def _validate_parties(
    db: AsyncSession, group_id: uuid.UUID, paid_by: uuid.UUID, paid_to: uuid.UUID
) -> None:
    if paid_by == paid_to:
        raise HTTPException(status_code=422, detail="Payer and payee must be different users")
    member_ids = set(
        (
            await db.execute(
                select(GroupMember.user_id).where(GroupMember.group_id == group_id)
            )
        ).scalars().all()
    )
    if paid_by not in member_ids or paid_to not in member_ids:
        raise HTTPException(
            status_code=400, detail="Both users must be members of the group"
        )


@router.get("/groups/{group_id}/settlements", response_model=list[SettlementOut])
async def list_settlements(
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    settlements = (
        await db.execute(
            select(Settlement)
            .where(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
            .order_by(Settlement.created_at.desc())
        )
    ).scalars().all()
    return settlements


@router.post(
    "/groups/{group_id}/settlements", response_model=SettlementOut, status_code=201
)
async def create_settlement(
    group_id: uuid.UUID,
    body: SettlementCreate,
    response: Response,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    await _validate_parties(db, group_id, body.paid_by_user_id, body.paid_to_user_id)
    _validate_amount_precision(body.amount, body.currency)
    settlement = Settlement(
        group_id=group_id,
        paid_by_user_id=body.paid_by_user_id,
        paid_to_user_id=body.paid_to_user_id,
        amount=body.amount,
        currency=body.currency,
        idempotency_key=idempotency_key,
    )
    db.add(settlement)
    try:
        await db.commit()
    except IntegrityError:
        # Idempotent replay: return the existing record with 200 OK.
        await db.rollback()
        existing = (
            await db.execute(
                select(Settlement).where(Settlement.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(status_code=400, detail="Settlement could not be created")
        response.status_code = 200
        return existing
    return settlement


@router.put("/settlements/{settlement_id}", response_model=SettlementOut)
async def update_settlement(
    settlement_id: uuid.UUID,
    body: SettlementUpdate,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    settlement = await get_settlement_for_member(db, settlement_id, caller)
    paid_by = body.paid_by_user_id or settlement.paid_by_user_id
    paid_to = body.paid_to_user_id or settlement.paid_to_user_id
    amount = body.amount if body.amount is not None else settlement.amount
    currency = body.currency or settlement.currency
    await _validate_parties(db, settlement.group_id, paid_by, paid_to)
    _validate_amount_precision(amount, currency)
    settlement.paid_by_user_id = paid_by
    settlement.paid_to_user_id = paid_to
    settlement.amount = amount
    settlement.currency = currency
    await db.commit()
    return settlement


@router.delete("/settlements/{settlement_id}", status_code=204)
async def delete_settlement(
    settlement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    settlement = await get_settlement_for_member(db, settlement_id, caller)
    settlement.deleted_at = datetime.now(timezone.utc)
    await db.commit()
