"""Volume brakes on row-creating endpoints: per-group ledger writes and
per-caller group creation."""

import uuid

import pytest
from conftest import expense_payload, idem, make_group, make_user

from _src import ratelimit
from _src.models import Expense, Settlement


def _settlement_payload(payer, payee, amount="5.00"):
    return {
        "paid_by_user_id": str(payer.id),
        "paid_to_user_id": str(payee.id),
        "amount": amount,
        "currency": "PLN",
    }


class TestLedgerWriteQuota:
    """Expense and settlement creation share one per-group window, so a
    client stuck in a retry loop cannot fill the database through whichever
    endpoint happens to be unguarded."""

    @pytest.fixture(autouse=True)
    def _small_quota(self, monkeypatch):
        monkeypatch.setattr(ratelimit, "MAX_LEDGER_WRITES_PER_GROUP", 3)

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

        # Soft-deleted rows keep their created_at and still count, so a
        # create/delete loop cannot reset the quota.
        for expense_id in created:
            assert (await client.delete(f"/api/expenses/{expense_id}")).status_code == 204

        blocked = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
        )
        assert blocked.status_code == 429

    async def test_the_limit_is_per_group(self, client, db_session, two_user_group):
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        for _ in range(3):
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )

        other = await make_group(db_session, g["alice"], g["bob"], name="Other")
        r = await client.post(
            f"/api/groups/{other.id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=idem(),
        )
        assert r.status_code == 201

    async def test_entries_outside_the_window_do_not_count(
        self, client, db_session, two_user_group
    ):
        g = two_user_group
        # Backdate three rows past the window; they must not consume quota.
        async with db_session() as s:
            for _ in range(3):
                s.add(
                    Expense(
                        group_id=g["group"].id,
                        description="Old",
                        category="General",
                        split_type="EQUAL",
                        total_amount=10,
                        currency="PLN",
                        paid_by_user_id=g["alice"].id,
                        idempotency_key=uuid.uuid4(),
                        created_at=ratelimit.window_cutoff(s)
                        - ratelimit.WRITE_WINDOW,
                    )
                )
            await s.commit()

        r = await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=idem(),
        )
        assert r.status_code == 201

    async def test_reads_and_edits_are_not_rate_limited(self, client, two_user_group):
        """The brake is on row creation. Fixing a typo on an existing expense
        must keep working after a group has hit its ceiling."""
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
    """Without this, the per-group ledger limit is sidestepped by making more
    groups."""

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

    async def test_groups_created_by_others_do_not_count(
        self, client, db_session, current_user
    ):
        alice = await make_user(db_session, "a@test.dev", "A")
        bob = await make_user(db_session, "b@test.dev", "B")
        await make_group(db_session, bob, alice, name="Bob's")
        await make_group(db_session, bob, alice, name="Bob's other")

        current_user.id = alice.id
        r = await client.post("/api/groups", json={"name": "Alice's first"})
        assert r.status_code == 201


async def test_settlement_quota_counts_settlements_too(client, db_session, two_user_group, monkeypatch):
    """Guards the pairing: the ledger window has to see settlements even when
    no expense was ever created in the group."""
    monkeypatch.setattr(ratelimit, "MAX_LEDGER_WRITES_PER_GROUP", 2)
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
