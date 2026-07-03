"""Database-aggregated net balances + greedy per-currency simplification (spec §3)."""

import uuid
from decimal import Decimal

from sqlalchemy import Select, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Expense, ExpenseSplit, Settlement


def _balance_stmt(group_id: uuid.UUID) -> Select:
    """Single SELECT with CTEs computing net balances on the database engine.

    Net Balance = paid (expenses) - owed (expense_splits)
                + sent (settlements) - received (settlements).
    Note: spec §3 v6 writes "+ received - sent", but that direction is
    inverted — a debtor settling their debt (sending cash) must move their
    net toward zero, and the creditor receiving that cash is owed less.
    Soft deletes are filtered independently on BOTH expenses and settlements.
    Built with Core (not a raw SQL string) so the same statement runs against
    Postgres in production and SQLite in the test suite.
    """
    paid = (
        select(
            Expense.paid_by_user_id.label("user_id"),
            Expense.currency.label("currency"),
            func.sum(Expense.total_amount).label("amt"),
        )
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by_user_id, Expense.currency)
        .cte("paid")
    )
    owed = (
        select(
            ExpenseSplit.user_id.label("user_id"),
            Expense.currency.label("currency"),
            func.sum(ExpenseSplit.owed_amount).label("amt"),
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(ExpenseSplit.user_id, Expense.currency)
        .cte("owed")
    )
    received = (
        select(
            Settlement.paid_to_user_id.label("user_id"),
            Settlement.currency.label("currency"),
            func.sum(Settlement.amount).label("amt"),
        )
        .where(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
        .group_by(Settlement.paid_to_user_id, Settlement.currency)
        .cte("received")
    )
    sent = (
        select(
            Settlement.paid_by_user_id.label("user_id"),
            Settlement.currency.label("currency"),
            func.sum(Settlement.amount).label("amt"),
        )
        .where(Settlement.group_id == group_id, Settlement.deleted_at.is_(None))
        .group_by(Settlement.paid_by_user_id, Settlement.currency)
        .cte("sent")
    )
    combined = union_all(
        select(paid.c.user_id, paid.c.currency, paid.c.amt),
        select(owed.c.user_id, owed.c.currency, (-owed.c.amt).label("amt")),
        select(received.c.user_id, received.c.currency, (-received.c.amt).label("amt")),
        select(sent.c.user_id, sent.c.currency, sent.c.amt),
    ).subquery("combined")
    return select(
        combined.c.user_id,
        combined.c.currency,
        func.sum(combined.c.amt).label("net"),
    ).group_by(combined.c.user_id, combined.c.currency)


async def net_balances(
    db: AsyncSession, group_id: uuid.UUID
) -> dict[str, dict[uuid.UUID, Decimal]]:
    """Net balance per (currency, user). Positive = is owed money."""
    rows = (await db.execute(_balance_stmt(group_id))).all()
    buckets: dict[str, dict[uuid.UUID, Decimal]] = {}
    for user_id, currency, net in rows:
        net = net if isinstance(net, Decimal) else Decimal(str(net))
        if net != 0:
            buckets.setdefault(currency, {})[user_id] = net
    return buckets


def greedy_simplify(
    buckets: dict[str, dict[uuid.UUID, Decimal]],
) -> dict[str, list[dict]]:
    """Per currency bucket: match largest debtor to largest creditor until all
    balances resolve to zero. Fully settles the group; not guaranteed to be the
    mathematical minimum number of transactions."""
    result: dict[str, list[dict]] = {}
    for currency, balances in buckets.items():
        debtors = sorted(
            ((u, -b) for u, b in balances.items() if b < 0),
            key=lambda x: (x[1], str(x[0])),
            reverse=True,
        )
        creditors = sorted(
            ((u, b) for u, b in balances.items() if b > 0),
            key=lambda x: (x[1], str(x[0])),
            reverse=True,
        )
        transfers = []
        di, ci = 0, 0
        debtors = [[u, amt] for u, amt in debtors]
        creditors = [[u, amt] for u, amt in creditors]
        while di < len(debtors) and ci < len(creditors):
            debtor, debt = debtors[di]
            creditor, credit = creditors[ci]
            amount = min(debt, credit)
            transfers.append(
                {"from_user_id": debtor, "to_user_id": creditor, "amount": amount}
            )
            debtors[di][1] -= amount
            creditors[ci][1] -= amount
            if debtors[di][1] == 0:
                di += 1
            if creditors[ci][1] == 0:
                ci += 1
        result[currency] = transfers
    return result
