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


class UserSearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
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


class MemberAdd(BaseModel):
    user_id: uuid.UUID


# ---------- Expenses ----------

class SplitInput(BaseModel):
    user_id: uuid.UUID
    amount: Decimal | None = None       # required for EXACT
    percentage: Decimal | None = None   # required for PERCENTAGE


class ExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    category: Category
    split_type: SplitType
    total_amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    paid_by_user_id: uuid.UUID
    expense_date: date | None = None  # defaults to today on the server
    splits: list[SplitInput] = Field(min_length=1)


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
    amount: Decimal = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class SettlementUpdate(BaseModel):
    paid_by_user_id: uuid.UUID | None = None
    paid_to_user_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0)
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
