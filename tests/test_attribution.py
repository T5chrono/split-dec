"""Who created and who last changed a ledger row.

Any member may create, edit and withdraw any expense or settlement in their
group — that is the shared-ledger model and it stays. What these pin is that
the act is now on the record, because the only person on the row used to be the
*payer*, which is a claim about money rather than a statement about authorship.
"""

import uuid

import pytest
from conftest import expense_payload, idem, make_user
from sqlalchemy import select

from _src.models import Expense, Settlement


async def _create_expense(client, group, payer, participants):
    return await client.post(
        f"/api/groups/{group.id}/expenses",
        json=expense_payload(payer, participants),
        headers=idem(),
    )


async def _row(db_session, model, row_id):
    async with db_session() as s:
        return await s.get(model, uuid.UUID(str(row_id)))


class TestExpenses:
    async def test_creation_records_the_author_not_just_the_payer(
        self, client, db_session, two_user_group
    ):
        """Alice enters an expense Bob paid for. The two are different people
        and the row has to say so."""
        g = two_user_group
        created = await _create_expense(client, g["group"], g["bob"], [g["alice"], g["bob"]])
        assert created.status_code == 201
        body = created.json()
        assert body["paid_by_user_id"] == str(g["bob"].id)
        assert body["created_by"] == str(g["alice"].id)
        assert body["updated_by"] is None
        assert body["updated_at"] is None

    async def test_an_edit_by_another_member_is_attributed(
        self, client, db_session, two_user_group, current_user
    ):
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()

        current_user.id = g["bob"].id
        patched = await client.patch(
            f"/api/expenses/{inv['id']}", json={"description": "Not what Alice wrote"}
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["created_by"] == str(g["alice"].id)
        assert body["updated_by"] == str(g["bob"].id)
        assert body["updated_at"] is not None

    async def test_a_financial_rewrite_is_attributed_too(
        self, client, db_session, two_user_group, current_user
    ):
        """The metadata path and the full splits rewrite are separate branches
        in update_expense; stamping only one of them would leave the edit that
        actually moves money unattributed."""
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()

        current_user.id = g["bob"].id
        patched = await client.patch(
            f"/api/expenses/{inv['id']}",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]], total_amount="300.00"),
        )
        assert patched.status_code == 200
        assert patched.json()["updated_by"] == str(g["bob"].id)
        assert patched.json()["total_amount"] == "300.0000"

    async def test_a_withdrawal_is_attributed(
        self, client, db_session, two_user_group, current_user
    ):
        """No screen shows a deleted row, so this stamp only ever answers a
        question asked afterwards — which is exactly why it has to be written
        at the time."""
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()

        current_user.id = g["bob"].id
        assert (await client.delete(f"/api/expenses/{inv['id']}")).status_code == 204

        row = await _row(db_session, Expense, inv["id"])
        assert row.deleted_at is not None
        assert row.updated_by == g["bob"].id
        assert row.created_by == g["alice"].id

    async def test_an_author_editing_their_own_row_is_still_recorded(
        self, client, db_session, two_user_group
    ):
        """Stored whoever the caller is. Whether it is *shown* is the UI's
        decision (ExpensesTab hides it when it matches the author), and the
        column must not pre-empt that by staying blank."""
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()
        patched = await client.patch(
            f"/api/expenses/{inv['id']}", json={"description": "Typo fixed"}
        )
        assert patched.json()["updated_by"] == str(g["alice"].id)
        assert patched.json()["created_by"] == str(g["alice"].id)

    async def test_a_patch_that_changes_nothing_is_not_an_edit(
        self, client, db_session, two_user_group, current_user
    ):
        """Bob opens Alice's expense, presses Save, changes nothing. The form
        sends a metadata body of identical values (ExpenseFormModal does this
        whenever the financials are untouched), and "edited by Bob" appearing
        from that is a false positive on the one signal this record gives."""
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()

        current_user.id = g["bob"].id
        for body in ({}, {"description": inv["description"], "category": inv["category"]}):
            patched = await client.patch(f"/api/expenses/{inv['id']}", json=body)
            assert patched.status_code == 200
            assert patched.json()["updated_by"] is None
            assert patched.json()["updated_at"] is None

    async def test_resubmitting_identical_financials_is_not_an_edit(
        self, client, two_user_group, current_user
    ):
        """The full splits rewrite is compared too — including the computed
        shares — so a caller echoing the stored expense back does not stamp."""
        g = two_user_group
        payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
        inv = (
            await client.post(
                f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
            )
        ).json()

        current_user.id = g["bob"].id
        patched = await client.patch(f"/api/expenses/{inv['id']}", json=payload)
        assert patched.status_code == 200
        assert patched.json()["updated_by"] is None

    async def test_one_changed_field_among_unchanged_ones_still_counts(
        self, client, two_user_group, current_user
    ):
        """The comparison must be an OR across fields, not a check of the last
        one assigned."""
        g = two_user_group
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()

        current_user.id = g["bob"].id
        patched = await client.patch(
            f"/api/expenses/{inv['id']}",
            json={"description": "Changed", "category": inv["category"]},
        )
        assert patched.json()["updated_by"] == str(g["bob"].id)

    async def test_a_replayed_creation_keeps_the_first_author(
        self, client, two_user_group, current_user
    ):
        """An Idempotency-Key replay returns the stored row. If Bob retries a
        request Alice's client had already landed, the author is still Alice."""
        g = two_user_group
        key = idem()
        first = await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=key,
        )
        assert first.status_code == 201

        current_user.id = g["bob"].id
        replay = await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=key,
        )
        assert replay.status_code == 200
        assert replay.json()["created_by"] == str(g["alice"].id)


class TestSettlements:
    async def _settle(self, client, group, payer, payee):
        return await client.post(
            f"/api/groups/{group.id}/settlements",
            json={
                "paid_by_user_id": str(payer.id),
                "paid_to_user_id": str(payee.id),
                "amount": "5.00",
                "currency": "PLN",
            },
            headers=idem(),
        )

    async def test_creation_records_the_author(self, client, two_user_group):
        """"I never recorded that payment" is at least as disputable as an
        edited amount, and `paid_by_user_id` does not answer it."""
        g = two_user_group
        body = (await self._settle(client, g["group"], g["bob"], g["alice"])).json()
        assert body["paid_by_user_id"] == str(g["bob"].id)
        assert body["created_by"] == str(g["alice"].id)
        assert body["updated_by"] is None

    async def test_an_edit_and_a_withdrawal_are_attributed(
        self, client, db_session, two_user_group, current_user
    ):
        g = two_user_group
        s = (await self._settle(client, g["group"], g["alice"], g["bob"])).json()

        current_user.id = g["bob"].id
        # Resubmitting the stored values is not an edit.
        echoed = await client.put(f"/api/settlements/{s['id']}", json={"amount": "5.00"})
        assert echoed.status_code == 200 and echoed.json()["updated_by"] is None

        edited = await client.put(f"/api/settlements/{s['id']}", json={"amount": "1.00"})
        assert edited.status_code == 200
        assert edited.json()["updated_by"] == str(g["bob"].id)

        assert (await client.delete(f"/api/settlements/{s['id']}")).status_code == 204
        row = await _row(db_session, Settlement, s["id"])
        assert row.deleted_at is not None and row.updated_by == g["bob"].id


class TestAttributionSurvivesTheEditor:
    async def test_an_edit_by_a_since_deleted_account_still_names_them(
        self, client, db_session, two_user_group, current_user
    ):
        """`updated_by` points at `public.users`, which account deletion
        anonymizes rather than deletes, so the reference stays valid and the
        edit reads as "Deleted user" — the same way the expenses a departed
        member took part in already do."""
        g = two_user_group
        carol = await make_user(db_session, "carol@test.dev", "Carol")
        # Carol joins, edits Alice's expense, then leaves entirely.
        inv = (await _create_expense(client, g["group"], g["alice"], [g["alice"], g["bob"]])).json()
        invitation = (
            await client.post(
                f"/api/groups/{g['group'].id}/invitations", json={"email": carol.email}
            )
        ).json()
        current_user.id = carol.id
        assert (await client.post(f"/api/invitations/{invitation['id']}/accept")).status_code == 204
        assert (
            await client.patch(f"/api/expenses/{inv['id']}", json={"description": "Carol's wording"})
        ).status_code == 200
        assert (await client.delete("/api/users/me")).status_code == 204

        row = await _row(db_session, Expense, inv["id"])
        assert row.updated_by == carol.id  # the row still names them

        current_user.id = g["alice"].id
        listed = (await client.get(f"/api/groups/{g['group'].id}/expenses")).json()["items"]
        assert listed[0]["updated_by"] == str(carol.id)


async def test_the_welcome_expense_has_an_author(client, db_session, current_user):
    """The deployment entered it on SplitDec's behalf. Leaving it blank would
    make "no author on record" ambiguous between that and a row older than the
    migration."""
    from _src.welcome import SYSTEM_USER_ID

    user = await make_user(db_session, "newcomer@test.dev", "Newcomer")
    current_user.id = user.id
    assert (await client.post("/api/users/me/welcome", json={"lang": "en"})).json()["created"]

    async with db_session() as s:
        expense = (await s.execute(select(Expense))).scalars().first()
    assert expense.created_by == SYSTEM_USER_ID
    assert expense.updated_by is None
