import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..currencies import precision_for
from ..db import get_db
from ..deps import (
    ensure_no_outsider_debt,
    get_settlement_for_member,
    record_edit,
    require_membership,
)
from ..models import GroupMember, Settlement
from ..ratelimit import (
    LEDGER,
    MUTATION,
    enforce_ledger_mutation_quota,
    enforce_ledger_write_quota,
    record_write,
)
from ..schemas import (
    SettlementCreate,
    SettlementListOut,
    SettlementOut,
    SettlementUpdate,
)

router = APIRouter(tags=["settlements"])


def _validate_amount_precision(amount: Decimal, currency: str) -> None:
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > precision_for(currency):
        raise HTTPException(
            status_code=422,
            detail=f"Amount has more decimal places than {currency} allows",
        )


async def _find_by_idempotency_key(
    db: AsyncSession, group_id: uuid.UUID, key: uuid.UUID
) -> Settlement | None:
    """Scoped to the path group on purpose: a key colliding with (or copied
    from) another group's request must never surface that group's record."""
    return (
        await db.execute(
            select(Settlement).where(
                Settlement.idempotency_key == key, Settlement.group_id == group_id
            )
        )
    ).scalar_one_or_none()


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


@router.get("/groups/{group_id}/settlements", response_model=SettlementListOut)
async def list_settlements(
    group_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Paged, like the expenses list and for the same reason.

    This one returned every settlement a group had ever recorded, in one
    response, on every load. Nothing caps how many accumulate: the per-caller
    ledger quota bounds the rate but not the total, and a group that runs for a
    couple of years with several members keeps all of them. It was the only
    list here that grows without a ceiling — pending invitations are held to
    one per address by the partial unique index, and a member list does not
    grow on its own.
    """
    await require_membership(db, group_id, caller)
    settlements = (
        await db.execute(
            select(Settlement)
            .where(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
            .order_by(Settlement.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return SettlementListOut(
        items=[SettlementOut.model_validate(s) for s in settlements],
        limit=limit,
        offset=offset,
    )


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
    await require_membership(db, group_id, caller, lock="shared")
    # Replay before quota — see the matching comment in expenses.py.
    replay = await _find_by_idempotency_key(db, group_id, idempotency_key)
    if replay is not None:
        response.status_code = 200
        return replay
    await enforce_ledger_write_quota(db, caller)
    await record_write(db, caller, LEDGER)  # committed with the settlement below
    await _validate_parties(db, group_id, body.paid_by_user_id, body.paid_to_user_id)
    _validate_amount_precision(body.amount, body.currency)
    settlement = Settlement(
        group_id=group_id,
        paid_by_user_id=body.paid_by_user_id,
        paid_to_user_id=body.paid_to_user_id,
        amount=body.amount,
        currency=body.currency,
        idempotency_key=idempotency_key,
        created_by=caller,
    )
    db.add(settlement)
    try:
        await db.commit()
    except IntegrityError:
        # Still reachable despite the pre-check above: two concurrent requests
        # carrying the same key can both miss it and race to insert.
        await db.rollback()
        existing = await _find_by_idempotency_key(db, group_id, idempotency_key)
        if existing is None:
            raise HTTPException(
                status_code=409, detail="Idempotency-Key is already in use"
            )
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
    settlement = await get_settlement_for_member(db, settlement_id, caller, lock="shared")
    # Charged before the work, not after: the point of this window is the
    # revalidation, the splits recompute and the balances read below, and a
    # caller who spends those must pay for them whether or not the request
    # turns out to alter anything. `record_edit` decides the separate question
    # of what gets *recorded* as an edit.
    await enforce_ledger_mutation_quota(db, caller)
    await record_write(db, caller, MUTATION)
    paid_by = body.paid_by_user_id or settlement.paid_by_user_id
    paid_to = body.paid_to_user_id or settlement.paid_to_user_id
    amount = body.amount if body.amount is not None else settlement.amount
    currency = body.currency or settlement.currency
    await _validate_parties(db, settlement.group_id, paid_by, paid_to)
    _validate_amount_precision(amount, currency)
    # Compared before assigning: a PUT that resubmits the stored values is not
    # an edit, and must not stamp one. See the matching note in expenses.py.
    changed = (
        settlement.paid_by_user_id != paid_by
        or settlement.paid_to_user_id != paid_to
        or settlement.amount != amount
        or settlement.currency != currency
    )
    settlement.paid_by_user_id = paid_by
    settlement.paid_to_user_id = paid_to
    settlement.amount = amount
    settlement.currency = currency
    if changed:
        record_edit(settlement, caller)
    # Both parties must be current members, so an edit that moves a settlement
    # off a former member leaves whatever they had settled unsettled again.
    await db.flush()
    await ensure_no_outsider_debt(db, settlement.group_id)
    await db.commit()
    return settlement


@router.delete("/settlements/{settlement_id}", status_code=204)
async def delete_settlement(
    settlement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    # Soft-deleting changes balances, so it must take the shared lock like
    # every other ledger mutation (serializes against member/group removal).
    settlement = await get_settlement_for_member(db, settlement_id, caller, lock="shared")
    await enforce_ledger_mutation_quota(db, caller)
    await record_write(db, caller, MUTATION)
    settlement.deleted_at = datetime.now(timezone.utc)
    record_edit(settlement, caller)
    await db.flush()
    # Withdrawing a settlement restores the debt it cleared — including one a
    # member cleared on their way out of the group.
    await ensure_no_outsider_debt(db, settlement.group_id)
    await db.commit()
