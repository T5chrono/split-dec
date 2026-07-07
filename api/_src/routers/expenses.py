import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..db import get_db
from ..deps import get_expense_for_member, require_membership
from ..models import Expense, ExpenseSplit, GroupMember
from ..schemas import ExpenseCreate, ExpenseListOut, ExpenseOut, ExpenseUpdate
from ..splits import compute_splits

router = APIRouter(tags=["expenses"])


async def _validate_participants(
    db: AsyncSession, group_id: uuid.UUID, body: ExpenseCreate | ExpenseUpdate
) -> None:
    """The payer and every split participant must be active group members."""
    member_ids = set(
        (
            await db.execute(
                select(GroupMember.user_id).where(GroupMember.group_id == group_id)
            )
        ).scalars().all()
    )
    involved = {body.paid_by_user_id, *(s.user_id for s in body.splits)}
    outsiders = involved - member_ids
    if outsiders:
        raise HTTPException(
            status_code=400, detail="All participants must be members of the group"
        )


@router.get("/groups/{group_id}/expenses", response_model=ExpenseListOut)
async def list_expenses(
    group_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller)
    expenses = (
        await db.execute(
            select(Expense)
            .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().unique().all()
    return ExpenseListOut(
        items=[ExpenseOut.model_validate(e) for e in expenses],
        limit=limit,
        offset=offset,
    )


@router.post("/groups/{group_id}/expenses", response_model=ExpenseOut, status_code=201)
async def create_expense(
    group_id: uuid.UUID,
    body: ExpenseCreate,
    response: Response,
    idempotency_key: uuid.UUID = Header(alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    await require_membership(db, group_id, caller, lock="shared")
    await _validate_participants(db, group_id, body)
    shares = compute_splits(
        body.split_type, body.total_amount, body.currency, body.paid_by_user_id, body.splits
    )
    expense = Expense(
        group_id=group_id,
        description=body.description,
        category=body.category.value,
        split_type=body.split_type,
        total_amount=body.total_amount,
        currency=body.currency,
        paid_by_user_id=body.paid_by_user_id,
        expense_date=body.expense_date or date.today(),
        idempotency_key=idempotency_key,
        splits=[
            ExpenseSplit(user_id=user_id, owed_amount=amount)
            for user_id, amount in shares.items()
        ],
    )
    db.add(expense)
    try:
        await db.commit()
    except IntegrityError:
        # Idempotent replay: return the existing record with 200 OK.
        await db.rollback()
        existing = (
            await db.execute(
                select(Expense).where(Expense.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if existing is None:
            raise HTTPException(status_code=400, detail="Expense could not be created")
        response.status_code = 200
        return ExpenseOut.model_validate(existing)
    return ExpenseOut.model_validate(expense)


@router.patch("/expenses/{expense_id}", response_model=ExpenseOut)
async def update_expense(
    expense_id: uuid.UUID,
    body: ExpenseUpdate,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Partial update. Metadata (description, category, expense_date) applies
    independently; the split-affecting fields travel as an all-or-nothing
    group and trigger a full rewrite of expense_splits (spec §4)."""
    expense = await get_expense_for_member(db, expense_id, caller, lock="shared")

    split_fields = (
        body.split_type,
        body.total_amount,
        body.currency,
        body.paid_by_user_id,
        body.splits,
    )
    if any(f is not None for f in split_fields):
        if any(f is None for f in split_fields):
            raise HTTPException(
                status_code=422,
                detail=(
                    "split_type, total_amount, currency, paid_by_user_id and "
                    "splits must be provided together"
                ),
            )
        await _validate_participants(db, expense.group_id, body)
        shares = compute_splits(
            body.split_type, body.total_amount, body.currency, body.paid_by_user_id, body.splits
        )
        expense.split_type = body.split_type
        expense.total_amount = body.total_amount
        expense.currency = body.currency
        expense.paid_by_user_id = body.paid_by_user_id
        # Flush the orphan-deletion of the old splits BEFORE adding
        # replacements: the unit of work otherwise emits the new INSERTs
        # first, violating UNIQUE(expense_id, user_id) for any user who
        # stays in the split.
        expense.splits = []
        await db.flush()
        expense.splits = [
            ExpenseSplit(user_id=user_id, owed_amount=amount)
            for user_id, amount in shares.items()
        ]

    if body.description is not None:
        expense.description = body.description
    if body.category is not None:
        expense.category = body.category.value
    if body.expense_date is not None:
        expense.expense_date = body.expense_date

    await db.commit()
    await db.refresh(expense)
    return ExpenseOut.model_validate(expense)


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(
    expense_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    expense = await get_expense_for_member(db, expense_id, caller)
    expense.deleted_at = datetime.now(timezone.utc)
    await db.commit()
