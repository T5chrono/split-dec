"""Volume brakes on row-creating endpoints: ledger writes and group creation,
both per caller, both counted from the `write_events` tombstone so that
deleting the rows they were charged for does not hand the slot back."""

import uuid

import pytest
from conftest import expense_payload, idem, make_group, make_user
from sqlalchemy import select

from _src import ratelimit
from _src.models import Settlement, WriteEvent


def _settlement_payload(payer, payee, amount="5.00"):
    return {
        "paid_by_user_id": str(payer.id),
        "paid_to_user_id": str(payee.id),
        "amount": amount,
        "currency": "PLN",
    }


async def _backdate_slots(db_session, user, count, kind=ratelimit.LEDGER):
    """Charge `count` slots that have already aged out of the window."""
    async with db_session() as s:
        for _ in range(count):
            s.add(
                WriteEvent(
                    user_id=user.id,
                    kind=kind,
                    created_at=ratelimit.window_cutoff(s) - ratelimit.WRITE_WINDOW,
                )
            )
        await s.commit()


async def _slots(db_session, user):
    async with db_session() as s:
        return (
            await s.execute(select(WriteEvent).where(WriteEvent.user_id == user.id))
        ).scalars().all()


class TestLedgerWriteQuota:
    """Expense and settlement creation share one per-caller window, so a
    client stuck in a retry loop cannot fill the database through whichever
    endpoint happens to be unguarded."""

    @pytest.fixture(autouse=True)
    def _small_quota(self, monkeypatch):
        monkeypatch.setattr(ratelimit, "MAX_LEDGER_WRITES_PER_CALLER", 3)

    async def test_expense_creation_stops_at_the_limit(self, client, two_user_group):
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])

        for _ in range(3):
            r = await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )
            assert r.status_code == 201

        blocked = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
        )
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]

    async def test_expenses_and_settlements_share_the_window(self, client, two_user_group):
        g = two_user_group
        for _ in range(2):
            r = await client.post(
                f"/api/groups/{g['group'].id}/expenses",
                json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
                headers=idem(),
            )
            assert r.status_code == 201

        # Third write in the window: allowed, but it is the last one.
        ok = await client.post(
            f"/api/groups/{g['group'].id}/settlements",
            json=_settlement_payload(g["bob"], g["alice"]),
            headers=idem(),
        )
        assert ok.status_code == 201

        blocked = await client.post(
            f"/api/groups/{g['group'].id}/settlements",
            json=_settlement_payload(g["bob"], g["alice"]),
            headers=idem(),
        )
        assert blocked.status_code == 429

    async def test_deleting_entries_does_not_free_the_window(self, client, two_user_group):
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])

        created = []
        for _ in range(3):
            r = await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )
            assert r.status_code == 201
            created.append(r.json()["id"])

        for expense_id in created:
            assert (await client.delete(f"/api/expenses/{expense_id}")).status_code == 204

        blocked = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
        )
        assert blocked.status_code == 429

    async def test_deleting_the_group_does_not_free_the_window(
        self, client, db_session, two_user_group
    ):
        """The tombstone's whole reason for existing. Deleting a group is a
        hard delete that takes its expenses and settlements with it, so while
        the quota counted those rows, anyone willing to churn groups had an
        unlimited ledger."""
        g = two_user_group
        # Alice is the sole participant, so the group nets to zero and is
        # deletable — exactly the state a churning client would arrange.
        payload = expense_payload(g["alice"], [g["alice"]])
        for _ in range(3):
            r = await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )
            assert r.status_code == 201

        assert (await client.delete(f"/api/groups/{g['group'].id}")).status_code == 204

        fresh = await make_group(db_session, g["alice"], g["bob"], name="Round two")
        blocked = await client.post(
            f"/api/groups/{fresh.id}/expenses",
            json=expense_payload(g["alice"], [g["alice"]]),
            headers=idem(),
        )
        assert blocked.status_code == 429

    async def test_replaying_at_the_ceiling_still_returns_the_existing_row(
        self, client, two_user_group
    ):
        """A client retrying a request whose response it never saw has already
        spent its slot. 429 there would leave it unable to find out whether the
        entry exists — the one thing Idempotency-Key is for."""
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        key = idem()

        first = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key
        )
        assert first.status_code == 201
        for _ in range(2):  # fill the window to the limit
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )

        replay = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key
        )
        assert replay.status_code == 200
        assert replay.json()["id"] == first.json()["id"]

    async def test_a_replay_is_not_charged_twice(self, client, db_session, two_user_group):
        """The replay returns before the quota is consulted, so it must not
        add a second tombstone for a row that already paid for one."""
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        key = idem()

        assert (
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key
            )
        ).status_code == 201
        assert (
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key
            )
        ).status_code == 200

        assert len(await _slots(db_session, g["alice"])) == 1

    async def test_a_rejected_write_is_not_charged(self, client, db_session, two_user_group):
        """The charge is added to the session before validation runs, so a 400
        has to take it back out with the rest of the transaction."""
        g = two_user_group
        outsider = await make_user(db_session, "outsider@test.dev", "Outsider")

        rejected = await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], outsider]),
            headers=idem(),
        )
        assert rejected.status_code == 400
        assert await _slots(db_session, g["alice"]) == []

    async def test_the_limit_is_per_caller_not_per_group(
        self, client, db_session, two_user_group, current_user
    ):
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        for _ in range(3):
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )

        # Another group is not a fresh window for the same caller...
        other = await make_group(db_session, g["alice"], g["bob"], name="Other")
        blocked = await client.post(
            f"/api/groups/{other.id}/expenses", json=payload, headers=idem()
        )
        assert blocked.status_code == 429

        # ...and Bob's allowance was never Alice's to spend. Under the old
        # per-group window, one busy member locked the whole group out.
        current_user.id = g["bob"].id
        ok = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
        )
        assert ok.status_code == 201

    async def test_slots_outside_the_window_do_not_count(
        self, client, db_session, two_user_group
    ):
        g = two_user_group
        await _backdate_slots(db_session, g["alice"], 3)

        r = await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=idem(),
        )
        assert r.status_code == 201

    async def test_aged_out_slots_are_pruned_on_the_next_write(
        self, client, db_session, two_user_group
    ):
        """Nothing retires these rows on a schedule — a serverless function has
        nowhere to hang a cron — so each write sweeps its own caller's."""
        g = two_user_group
        await _backdate_slots(db_session, g["alice"], 3)

        await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=idem(),
        )

        remaining = await _slots(db_session, g["alice"])
        assert len(remaining) == 1  # the three stale ones swept, the new one charged

    async def test_reads_and_edits_are_not_rate_limited(self, client, two_user_group):
        """The brake is on row creation. Fixing a typo on an existing expense
        must keep working after a caller has hit their ceiling."""
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        ids = []
        for _ in range(3):
            r = await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )
            ids.append(r.json()["id"])

        assert (await client.get(f"/api/groups/{g['group'].id}/expenses")).status_code == 200
        assert (await client.get(f"/api/groups/{g['group'].id}/balances")).status_code == 200
        edit = await client.patch(f"/api/expenses/{ids[0]}", json={"description": "Fixed"})
        assert edit.status_code == 200


class TestGroupCreationQuota:
    """Without this, the ledger limit is sidestepped by making more groups."""

    @pytest.fixture(autouse=True)
    def _small_quota(self, monkeypatch):
        monkeypatch.setattr(ratelimit, "MAX_GROUPS_PER_CALLER", 2)

    async def test_group_creation_stops_at_the_limit(self, client, db_session, current_user):
        alice = await make_user(db_session, "solo@test.dev", "Solo")
        current_user.id = alice.id

        for i in range(2):
            r = await client.post("/api/groups", json={"name": f"Trip {i}"})
            assert r.status_code == 201

        blocked = await client.post("/api/groups", json={"name": "One too many"})
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]

    async def test_deleting_groups_does_not_free_the_window(
        self, client, db_session, current_user
    ):
        """Group creation counted the groups themselves, which a delete
        removed — the same reset loop the ledger window had."""
        alice = await make_user(db_session, "churn@test.dev", "Churn")
        current_user.id = alice.id

        created = []
        for i in range(2):
            r = await client.post("/api/groups", json={"name": f"Trip {i}"})
            assert r.status_code == 201
            created.append(r.json()["id"])

        for group_id in created:  # empty, so nothing to settle first
            assert (await client.delete(f"/api/groups/{group_id}")).status_code == 204

        blocked = await client.post("/api/groups", json={"name": "Round two"})
        assert blocked.status_code == 429

    async def test_groups_created_by_others_do_not_count(
        self, client, db_session, current_user
    ):
        alice = await make_user(db_session, "a@test.dev", "A")
        bob = await make_user(db_session, "b@test.dev", "B")

        current_user.id = bob.id
        for i in range(2):
            assert (
                await client.post("/api/groups", json={"name": f"Bob's {i}"})
            ).status_code == 201

        current_user.id = alice.id
        r = await client.post("/api/groups", json={"name": "Alice's first"})
        assert r.status_code == 201

    async def test_the_two_windows_are_separate(self, client, db_session, current_user):
        """A burst of expenses must not consume the allowance for creating a
        group, or one busy trip would block starting the next one."""
        alice = await make_user(db_session, "mixed@test.dev", "Mixed")
        bob = await make_user(db_session, "mixed-bob@test.dev", "Bob")
        group = await make_group(db_session, alice, bob)
        current_user.id = alice.id

        for _ in range(3):
            assert (
                await client.post(
                    f"/api/groups/{group.id}/expenses",
                    json=expense_payload(alice, [alice, bob]),
                    headers=idem(),
                )
            ).status_code == 201

        assert (await client.post("/api/groups", json={"name": "Next"})).status_code == 201


async def test_settlement_quota_counts_settlements_too(
    client, db_session, two_user_group, monkeypatch
):
    """Guards the pairing: the ledger window has to see settlements even when
    no expense was ever created in the group."""
    monkeypatch.setattr(ratelimit, "MAX_LEDGER_WRITES_PER_CALLER", 2)
    g = two_user_group

    for _ in range(2):
        r = await client.post(
            f"/api/groups/{g['group'].id}/settlements",
            json=_settlement_payload(g["bob"], g["alice"]),
            headers=idem(),
        )
        assert r.status_code == 201

    blocked = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=_settlement_payload(g["bob"], g["alice"]),
        headers=idem(),
    )
    assert blocked.status_code == 429

    async with db_session() as s:
        assert (await s.get(Settlement, uuid.UUID(r.json()["id"]))) is not None
