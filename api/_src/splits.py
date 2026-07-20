"""Split verification and currency-precision math (spec §3)."""

import uuid
from decimal import ROUND_HALF_EVEN, Decimal

from fastapi import HTTPException

from .currencies import precision_for


def _quantum(precision: int) -> Decimal:
    return Decimal(1).scaleb(-precision)  # 10^-precision, e.g. 0.01


def _round_bankers(value: Decimal, precision: int) -> Decimal:
    return value.quantize(_quantum(precision), rounding=ROUND_HALF_EVEN)


def _distribute_remainder(
    shares: dict[uuid.UUID, Decimal],
    total: Decimal,
    order: list[uuid.UUID],
    precision: int,
) -> dict[uuid.UUID, Decimal]:
    """Adjust rounded shares one smallest currency unit at a time, starting
    with the paying user, until the shares sum exactly to `total`.

    Shares must stay non-negative (Pydantic + a DB CHECK enforce it): when
    units are being *removed*, a participant whose rounded share is already
    below one unit is skipped and the next one in `order` takes the hit.
    Otherwise a percentage split like USD 0.02 as 0/33.33/33.33/33.34 pushes
    the payer to -0.01. Termination is guaranteed: removal only runs while
    sum(shares) > total >= 0, so at least one share is >= one unit."""
    unit = _quantum(precision)
    diff = total - sum(shares.values())
    step = unit if diff > 0 else -unit
    i = 0
    while diff != 0:
        user_id = order[i % len(order)]
        i += 1
        if shares[user_id] + step < 0:
            continue
        shares[user_id] += step
        diff -= step
    return shares


def compute_splits(
    split_type: str,
    total_amount: Decimal,
    currency: str,
    paid_by_user_id: uuid.UUID,
    splits_input: list,  # list of schemas.SplitInput
) -> dict[uuid.UUID, Decimal]:
    """Return the exact owed_amount per participant. Sum always == total_amount."""
    precision = precision_for(currency)
    if total_amount != _round_bankers(total_amount, precision):
        raise HTTPException(
            status_code=422,
            detail=f"total_amount has more decimal places than {currency} allows",
        )

    participants = [s.user_id for s in splits_input]
    if not participants:
        raise HTTPException(status_code=422, detail="At least one split participant is required")
    if len(set(participants)) != len(participants):
        raise HTTPException(status_code=422, detail="Duplicate user in splits")

    # Deterministic distribution order: payer first, then others sorted by id.
    order = sorted(participants, key=lambda u: (u != paid_by_user_id, str(u)))

    if split_type == "EQUAL":
        share = _round_bankers(total_amount / len(participants), precision)
        shares = {u: share for u in participants}
        return _distribute_remainder(shares, total_amount, order, precision)

    if split_type == "EXACT":
        shares = {}
        for s in splits_input:
            if s.amount is None:
                raise HTTPException(
                    status_code=422, detail="EXACT split requires an amount for every user"
                )
            if s.amount != _round_bankers(s.amount, precision):
                raise HTTPException(
                    status_code=422,
                    detail=f"Split amount has more decimal places than {currency} allows",
                )
            shares[s.user_id] = s.amount
        if sum(shares.values()) != total_amount:
            raise HTTPException(
                status_code=422, detail="Sum of exact amounts must equal total_amount"
            )
        return shares

    if split_type == "PERCENTAGE":
        percentages = {}
        for s in splits_input:
            if s.percentage is None:
                raise HTTPException(
                    status_code=422, detail="PERCENTAGE split requires a percentage for every user"
                )
            percentages[s.user_id] = s.percentage
        if sum(percentages.values()) != Decimal(100):
            raise HTTPException(status_code=422, detail="Percentages must sum to 100")
        shares = {
            u: _round_bankers(total_amount * pct / Decimal(100), precision)
            for u, pct in percentages.items()
        }
        return _distribute_remainder(shares, total_amount, order, precision)

    raise HTTPException(status_code=422, detail=f"Unknown split_type: {split_type}")
