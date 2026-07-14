"""Optional integration test: group row locks against real Postgres.

SQLite silently drops FOR SHARE/FOR UPDATE clauses, so the suite's regular
tests never execute them. Postgres, however, rejects locking clauses that
target the nullable side of an outer join at execution time — running the
locked helpers here catches a wrong `of=` target or an illegal join shape.

Skipped unless TEST_DATABASE_URL is set; everything runs inside a rolled-back
transaction.
"""

import os
import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from _src.deps import (
    get_expense_for_member,
    get_settlement_for_member,
    lock_groups_exclusive,
    require_membership,
)
from _src.models import Expense, ExpenseSplit, Group, GroupMember, Settlement, User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"
)


async def test_locked_authorization_queries_execute_on_postgres():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        user_id = uuid.uuid4()
        db.add(User(id=user_id, email=f"lock-test-{user_id}@test.invalid"))
        group = Group(name="lock-test", created_by=user_id)
        db.add(group)
        await db.flush()
        db.add(GroupMember(group_id=group.id, user_id=user_id))
        expense = Expense(
            group_id=group.id, description="d", category="General",
            split_type="EQUAL", total_amount=D("10.00"), currency="PLN",
            paid_by_user_id=user_id, idempotency_key=uuid.uuid4(),
            splits=[ExpenseSplit(user_id=user_id, owed_amount=D("10.00"))],
        )
        settlement_peer = uuid.uuid4()
        db.add(User(id=settlement_peer, email=f"lock-peer-{settlement_peer}@test.invalid"))
        db.add(expense)
        settlement = Settlement(
            group_id=group.id, paid_by_user_id=user_id, paid_to_user_id=settlement_peer,
            amount=D("1.00"), currency="PLN", idempotency_key=uuid.uuid4(),
        )
        db.add(settlement)
        await db.flush()

        # Each of these executes its FOR SHARE / FOR UPDATE OF groups clause
        # for real; Postgres raises if the lock target is illegal.
        await require_membership(db, group.id, user_id, lock="exclusive")
        await require_membership(db, group.id, user_id, lock="shared")
        fetched_expense = await get_expense_for_member(
            db, expense.id, user_id, lock="shared"
        )
        assert fetched_expense.id == expense.id
        fetched_settlement = await get_settlement_for_member(
            db, settlement.id, user_id, lock="shared"
        )
        assert fetched_settlement.id == settlement.id

        # Bulk multi-group exclusive lock (delete_account path): a second
        # group makes the IN(...) + ORDER BY + FOR UPDATE shape real.
        group2 = Group(name="lock-test-2", created_by=user_id)
        db.add(group2)
        await db.flush()
        await lock_groups_exclusive(db, [group2.id, group.id])
        await lock_groups_exclusive(db, [])  # no-op path

        await db.rollback()  # never persist test rows
    await engine.dispose()
