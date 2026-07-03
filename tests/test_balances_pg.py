"""Optional integration test: the balance CTE against a real Postgres.

Skipped unless TEST_DATABASE_URL is set (use a disposable database or a
Supabase branch — the test creates and drops its own rows inside a
transaction that is always rolled back).

    TEST_DATABASE_URL=postgresql+asyncpg://... pytest tests/test_balances_pg.py
"""

import os
import uuid
from decimal import Decimal as D

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from _src.balances import net_balances
from _src.models import Expense, ExpenseSplit, Group, GroupMember, Settlement, User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set"
)


async def test_cte_against_postgres():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        u1, u2, u3 = (uuid.uuid4() for _ in range(3))
        db.add_all(
            [User(id=u, email=f"cte-test-{u}@test.invalid") for u in (u1, u2, u3)]
        )
        group = Group(name="cte-test", created_by=u1)
        db.add(group)
        await db.flush()
        db.add_all([GroupMember(group_id=group.id, user_id=u) for u in (u1, u2, u3)])
        db.add(
            Expense(
                group_id=group.id, description="d", category="General",
                split_type="EQUAL", total_amount=D("90.00"), currency="PLN",
                paid_by_user_id=u1, idempotency_key=uuid.uuid4(),
                splits=[
                    ExpenseSplit(user_id=u, owed_amount=D("30.00")) for u in (u1, u2, u3)
                ],
            )
        )
        db.add(
            Settlement(
                group_id=group.id, paid_by_user_id=u2, paid_to_user_id=u1,
                amount=D("10.00"), currency="PLN", idempotency_key=uuid.uuid4(),
            )
        )
        await db.flush()

        # u1 paid 90, owes 30, received 10 back -> owed 50.
        # u2 owes 30, settled 10 of it -> owes 20. u3 owes 30.
        buckets = await net_balances(db, group.id)
        assert buckets == {
            "PLN": {u1: D("50.00"), u2: D("-20.00"), u3: D("-30.00")}
        }
        await db.rollback()  # never persist test rows
    await engine.dispose()
