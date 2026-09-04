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
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from _src import ratelimit
from _src.deps import (
    get_active_user,
    get_expense_for_member,
    get_settlement_for_member,
    lock_groups_exclusive,
    require_membership,
)
from _src.models import (
    Expense,
    ExpenseSplit,
    Group,
    GroupMember,
    Settlement,
    User,
    WriteEvent,
)

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

        # User row locks (account deletion vs. membership creation).
        assert (await get_active_user(db, user_id, lock="shared")).id == user_id
        assert (await get_active_user(db, user_id, lock="exclusive")).id == user_id

        await db.rollback()  # never persist test rows
    await engine.dispose()


async def test_deletion_user_lock_does_not_block_fk_inserts():
    """delete_account's user lock must be FOR NO KEY UPDATE, not FOR UPDATE.

    Every insert referencing users.id (expense_splits, settlements, ...)
    takes FOR KEY SHARE on that row. FOR UPDATE conflicts with it, so a
    concurrent expense write — which already holds the group's shared lock —
    would deadlock against a deletion waiting for that same group. This test
    fails by hanging until the statement timeout if the lock mode regresses.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    user_id = uuid.uuid4()
    group_id = None
    async with Session() as setup:
        setup.add(User(id=user_id, email=f"lock-nokey-{user_id}@test.invalid"))
        group = Group(name="lock-nokey", created_by=user_id)
        setup.add(group)
        await setup.flush()
        setup.add(GroupMember(group_id=group.id, user_id=user_id))
        group_id = group.id
        await setup.commit()  # committed so a second session can see it

    try:
        async with Session() as deleter, Session() as writer:
            await get_active_user(deleter, user_id, lock="exclusive")
            # A different transaction inserts a row that references the
            # locked user. With FOR NO KEY UPDATE this proceeds immediately.
            await writer.execute(text("SET LOCAL lock_timeout = '5s'"))
            expense = Expense(
                group_id=group_id, description="d", category="General",
                split_type="EQUAL", total_amount=D("10.00"), currency="PLN",
                paid_by_user_id=user_id, idempotency_key=uuid.uuid4(),
                splits=[ExpenseSplit(user_id=user_id, owed_amount=D("10.00"))],
            )
            writer.add(expense)
            await writer.flush()
            await writer.rollback()
            await deleter.rollback()
    finally:
        async with Session() as cleanup:
            await cleanup.execute(
                delete(GroupMember).where(GroupMember.group_id == group_id)
            )
            await cleanup.execute(delete(Group).where(Group.id == group_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()
        await engine.dispose()


async def test_quota_window_lock_is_exclusive_between_transactions():
    """The write quotas count and then insert, two statements that are only a
    ceiling if something serializes them (ratelimit.py). That something is a
    transaction-scoped advisory lock, which SQLite never executes — here it
    runs for real, and a second transaction must wait for it.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    caller = uuid.uuid4()
    try:
        async with Session() as first, Session() as second:
            await ratelimit._hold_window(first, ratelimit.LEDGER, caller)

            # Same caller, same window: blocked until the first commits.
            await second.execute(text("SET LOCAL lock_timeout = '1s'"))
            with pytest.raises(DBAPIError):
                await ratelimit._hold_window(second, ratelimit.LEDGER, caller)
            await second.rollback()

            # A different caller, and the deployment-wide invitation window,
            # are separate locks — neither waits on the one held above.
            async with Session() as third:
                await third.execute(text("SET LOCAL lock_timeout = '1s'"))
                await ratelimit._hold_window(third, ratelimit.LEDGER, uuid.uuid4())
                await ratelimit._hold_window(third, ratelimit.INVITE, None)
                await third.rollback()

            await first.rollback()  # releases it
    finally:
        await engine.dispose()


async def test_prune_deletes_only_rows_it_can_lock():
    """record_write's sweep runs from every quota-consuming write, so it uses
    SKIP LOCKED and a deterministic order to step over rows another sweep is
    already taking. Neither clause exists on SQLite; this executes the real
    statement, and asserts a locked row survives instead of blocking.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    Session = async_sessionmaker(engine, expire_on_commit=False)
    caller = uuid.uuid4()
    aged = datetime.now(timezone.utc) - timedelta(days=2)
    try:
        async with Session() as setup:
            setup.add(User(id=caller, email=f"prune-{caller}@test.invalid"))
            for _ in range(2):
                setup.add(
                    WriteEvent(user_id=caller, kind=ratelimit.LEDGER, created_at=aged)
                )
            await setup.commit()

        async with Session() as holder, Session() as sweeper:
            # Hold one of the two aged rows.
            held = (
                await holder.execute(
                    select(WriteEvent.id)
                    .where(WriteEvent.user_id == caller)
                    .order_by(WriteEvent.id)
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one()

            await sweeper.execute(text("SET LOCAL lock_timeout = '5s'"))
            await ratelimit.record_write(sweeper, caller, ratelimit.LEDGER)
            await sweeper.commit()
            await holder.rollback()

        async with Session() as check:
            remaining = (
                await check.execute(
                    select(WriteEvent.id).where(WriteEvent.user_id == caller)
                )
            ).scalars().all()
        # The locked row was skipped, not waited on; the other aged row went,
        # and the freshly charged one stays.
        assert held in remaining
        assert len(remaining) == 2
    finally:
        async with Session() as cleanup:
            await cleanup.execute(delete(WriteEvent).where(WriteEvent.user_id == caller))
            await cleanup.execute(delete(User).where(User.id == caller))
            await cleanup.commit()
        await engine.dispose()


async def test_the_account_deletion_wrapper_is_callable_by_the_app_role():
    """routers/users.py's Postgres branch, which the SQLite suite never runs.

    Account deletion removes the caller's `auth.users` row, and since
    20260904100000 the app connects as `splitdec_app`, which has no privileges
    in the `auth` schema -- it goes through the SECURITY DEFINER wrapper
    `public.delete_auth_user` instead. Everything about that arrangement lives
    outside the models the rest of the suite builds its schema from: the
    function is created by a migration, and the EXECUTE grant is a catalog
    entry. So the only way to find out that the grant was forgotten, or that
    the wrapper was never applied, is to call it.

    Deliberately called with a random uuid: the DELETE matches nothing, so this
    proves the privilege without needing an auth user to destroy. A missing
    grant surfaces as `permission denied for function delete_auth_user`, a
    missing function as `UndefinedFunctionError`.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
    )
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await db.execute(
                text("SELECT public.delete_auth_user(:uid)"), {"uid": str(uuid.uuid4())}
            )
            await db.rollback()
    finally:
        await engine.dispose()
