import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from .categories import Category

SplitType = Literal["EQUAL", "EXACT", "PERCENTAGE"]


def money(value: Decimal) -> str:
    """Serialize NUMERIC(14,4) as a string with 4 decimal places, e.g. "120.5000"."""
    return format(value.quantize(Decimal("0.0001")), "f")


# ---------- Users ----------

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None


# ---------- Groups ----------

class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime


class GroupDetailOut(GroupOut):
    members: list[UserOut]


class InvitationCreate(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)


class InvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    email: str
    status: str
    invited_user_id: uuid.UUID | None
    created_at: datetime


class InvitationCreatedOut(InvitationOut):
    user_exists: bool
    email_sent: bool


class MyInvitationOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    invited_by_name: str | None
    created_at: datetime


# ---------- Expenses ----------

class SplitInput(BaseModel):
    user_id: uuid.UUID
    # Non-negative: negative obligations would let a crafted split satisfy the
    # sum check while shifting money arbitrarily between members.
    # max_digits/decimal_places mirror the NUMERIC(14,4) columns so range
    # violations are 422s, not database errors.
    amount: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    percentage: Decimal | None = Field(
        default=None, ge=0, le=100, max_digits=7, decimal_places=4
    )


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    category: Category
    split_type: SplitType
    total_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    paid_by_user_id: uuid.UUID
    expense_date: date | None = None  # defaults to today on the server
    splits: list[SplitInput] = Field(min_length=1)


class ExpenseUpdate(BaseModel):
    """Partial update. Metadata fields apply independently; the five
    split-affecting fields must be provided together (or not at all) so the
    splits always stay consistent with the amount, currency, and payer."""

    description: str | None = Field(default=None, min_length=1, max_length=500)
    category: Category | None = None
    split_type: SplitType | None = None
    total_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=14, decimal_places=4
    )
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    paid_by_user_id: uuid.UUID | None = None
    expense_date: date | None = None
    splits: list[SplitInput] | None = Field(default=None, min_length=1)


class ExpenseSplitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    owed_amount: Decimal

    @field_serializer("owed_amount")
    def _ser_owed(self, v: Decimal) -> str:
        return money(v)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    description: str
    category: str
    split_type: str
    total_amount: Decimal
    currency: str
    paid_by_user_id: uuid.UUID
    expense_date: date
    created_at: datetime
    splits: list[ExpenseSplitOut]

    @field_serializer("total_amount")
    def _ser_total(self, v: Decimal) -> str:
        return money(v)


class ExpenseListOut(BaseModel):
    items: list[ExpenseOut]
    limit: int
    offset: int


# ---------- Settlements ----------

class SettlementCreate(BaseModel):
    paid_by_user_id: uuid.UUID
    paid_to_user_id: uuid.UUID
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class SettlementUpdate(BaseModel):
    paid_by_user_id: uuid.UUID | None = None
    paid_to_user_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=4)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    paid_by_user_id: uuid.UUID
    paid_to_user_id: uuid.UUID
    amount: Decimal
    currency: str
    created_at: datetime

    @field_serializer("amount")
    def _ser_amount(self, v: Decimal) -> str:
        return money(v)


# ---------- Balances ----------

class BalanceTransfer(BaseModel):
    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    amount: Decimal

    @field_serializer("amount")
    def _ser_amount(self, v: Decimal) -> str:
        return money(v)
