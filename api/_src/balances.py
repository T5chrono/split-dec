"""Database-aggregated net balances + greedy per-currency simplification (spec §3)."""

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Net Balance = paid (expenses) - owed (expense_splits)
#             + received (settlements) - sent (settlements),
# computed entirely on the database engine. Soft deletes are filtered
# independently on BOTH expenses and settlements.
_BALANCE_SQL = text("""
WITH paid AS (
  SELECT paid_by_user_id AS user_id, currency, SUM(total_amount) AS amt
  FROM expenses
  WHERE group_id = :group_id AND deleted_at IS NULL
  GROUP BY 1, 2
),
owed AS (
  SELECT es.user_id, e.currency, SUM(es.owed_amount) AS amt
  FROM expense_splits es
  JOIN expenses e ON e.id = es.expense_id
  WHERE e.group_id = :group_id AND e.deleted_at IS NULL
  GROUP BY 1, 2
),
received AS (
  SELECT paid_to_user_id AS user_id, currency, SUM(amount) AS amt
  FROM settlements
  WHERE group_id = :group_id AND deleted_at IS NULL
  GROUP BY 1, 2
),
sent AS (
  SELECT paid_by_user_id AS user_id, currency, SUM(amount) AS amt
  FROM settlements
  WHERE group_id = :group_id AND deleted_at IS NULL
  GROUP BY 1, 2
)
SELECT user_id, currency, SUM(amt) AS net
FROM (
  SELECT user_id, currency, amt FROM paid
  UNION ALL SELECT user_id, currency, -amt FROM owed
  UNION ALL SELECT user_id, currency, amt FROM received
  UNION ALL SELECT user_id, currency, -amt FROM sent
) combined
GROUP BY user_id, currency
""")


async def net_balances(
    db: AsyncSession, group_id: uuid.UUID
) -> dict[str, dict[uuid.UUID, Decimal]]:
    """Net balance per (currency, user). Positive = is owed money."""
    rows = (await db.execute(_BALANCE_SQL, {"group_id": group_id})).all()
    buckets: dict[str, dict[uuid.UUID, Decimal]] = {}
    for user_id, currency, net in rows:
        if net != 0:
            buckets.setdefault(currency, {})[user_id] = Decimal(net)
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
