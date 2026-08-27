"""Expense lifecycle through the API: create, idempotency, edit, soft delete."""

import uuid

from conftest import expense_payload, idem


async def test_create_expense(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["total_amount"] == "30.0000"  # money serialized as string
    assert sorted(s["owed_amount"] for s in body["splits"]) == ["15.0000", "15.0000"]


async def test_create_is_idempotent(client, two_user_group):
    g = two_user_group
    key = idem()
    payload = expense_payload(g["alice"], [g["alice"], g["bob"]])
    first = await client.post(f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key)
    replay = await client.post(f"/api/groups/{g['group'].id}/expenses", json=payload, headers=key)
    assert first.status_code == 201
    assert replay.status_code == 200  # replay returns existing data
    assert replay.json()["id"] == first.json()["id"]


async def test_missing_idempotency_key_rejected(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
    )
    assert r.status_code == 422


async def test_non_member_participant_rejected(client, two_user_group, db_session):
    from conftest import make_user

    g = two_user_group
    stranger = await make_user(db_session, "stranger@test.dev")
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], stranger]),
        headers=idem(),
    )
    assert r.status_code == 400


async def test_exact_split_mismatch_rejected(client, two_user_group):
    g = two_user_group
    payload = expense_payload(
        g["alice"], [g["alice"], g["bob"]],
        split_type="EXACT",
        splits=[
            {"user_id": str(g["alice"].id), "amount": "10.00"},
            {"user_id": str(g["bob"].id), "amount": "10.00"},
        ],
    )
    r = await client.post(f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem())
    assert r.status_code == 422


async def test_negative_exact_amount_rejected(client, two_user_group):
    """Negative obligations would satisfy the sum check while shifting money
    arbitrarily: [40, -10] sums to 30 but gives bob a negative debt."""
    g = two_user_group
    payload = expense_payload(
        g["alice"], [g["alice"], g["bob"]],
        split_type="EXACT",
        total_amount="30.00",
        splits=[
            {"user_id": str(g["alice"].id), "amount": "40.00"},
            {"user_id": str(g["bob"].id), "amount": "-10.00"},
        ],
    )
    r = await client.post(f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem())
    assert r.status_code == 422


async def test_out_of_range_percentages_rejected(client, two_user_group):
    g = two_user_group
    for pcts in (("150", "-50"), ("-20", "120")):
        payload = expense_payload(
            g["alice"], [g["alice"], g["bob"]],
            split_type="PERCENTAGE",
            splits=[
                {"user_id": str(g["alice"].id), "percentage": pcts[0]},
                {"user_id": str(g["bob"].id), "percentage": pcts[1]},
            ],
        )
        r = await client.post(
            f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem()
        )
        assert r.status_code == 422, pcts


async def test_amount_exceeding_numeric_range_rejected(client, two_user_group):
    """NUMERIC(14,4) can hold at most 10 integer digits; larger inputs must
    be a 422, not a database error."""
    g = two_user_group
    payload = expense_payload(g["alice"], [g["alice"]], total_amount="99999999999.00")
    r = await client.post(f"/api/groups/{g['group'].id}/expenses", json=payload, headers=idem())
    assert r.status_code == 422


async def test_idempotency_replay_is_scoped_to_the_group(client, two_user_group):
    """A key used in another group must 409, never return that group's record."""
    g = two_user_group
    key = idem()
    first = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=key,
    )
    assert first.status_code == 201

    other = await client.post("/api/groups", json={"name": "Other group"})
    r = await client.post(
        f"/api/groups/{other.json()['id']}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=key,  # same Idempotency-Key, different group
    )
    assert r.status_code == 409
    assert "Idempotency-Key" in r.json()["detail"]


async def test_invalid_category_rejected(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]], category="Bribes"),
        headers=idem(),
    )
    assert r.status_code == 422


async def test_edit_rewrites_splits_with_overlapping_users(client, two_user_group):
    """Regression: PATCH previously 500'd on UNIQUE(expense_id, user_id)."""
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    expense_id = created.json()["id"]

    r = await client.patch(
        f"/api/expenses/{expense_id}",
        json=expense_payload(
            g["alice"], [g["alice"], g["bob"]],
            description="Dinner (corrected)", total_amount="32.00",
        ),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["description"] == "Dinner (corrected)"
    assert body["total_amount"] == "32.0000"
    assert sorted(s["owed_amount"] for s in body["splits"]) == ["16.0000", "16.0000"]
    assert len(body["splits"]) == 2  # no leftover rows from before the edit


async def test_edit_can_change_participants_and_split_type(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}",
        json=expense_payload(
            g["bob"], [g["bob"]],
            split_type="EXACT",
            splits=[{"user_id": str(g["bob"].id), "amount": "30.00"}],
        ),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["paid_by_user_id"] == str(g["bob"].id)
    assert body["splits"] == [{"user_id": str(g["bob"].id), "owed_amount": "30.0000"}]


async def test_soft_delete_hides_expense_and_clears_balances(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    expense_id = created.json()["id"]

    r = await client.delete(f"/api/expenses/{expense_id}")
    assert r.status_code == 204

    listing = await client.get(f"/api/groups/{g['group'].id}/expenses")
    assert listing.json()["items"] == []

    balances = await client.get(f"/api/groups/{g['group'].id}/balances")
    assert all(v == [] for v in balances.json().values())

    # Deleted expense is gone for edit/delete purposes too.
    assert (await client.delete(f"/api/expenses/{expense_id}")).status_code == 404


async def test_pagination_and_ordering(client, two_user_group):
    g = two_user_group
    for i in range(3):
        await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"]], description=f"e{i}"),
            headers=idem(),
        )
    page = await client.get(f"/api/groups/{g['group'].id}/expenses?limit=2&offset=0")
    body = page.json()
    assert len(body["items"]) == 2 and body["limit"] == 2 and body["offset"] == 0
    rest = await client.get(f"/api/groups/{g['group'].id}/expenses?limit=2&offset=2")
    assert len(rest.json()["items"]) == 1


async def test_filter_by_payer(client, two_user_group):
    g = two_user_group
    for payer, description in ((g["alice"], "a1"), (g["bob"], "b1"), (g["alice"], "a2")):
        await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(payer, [g["alice"], g["bob"]], description=description),
            headers=idem(),
        )

    mine = await client.get(f"/api/groups/{g['group'].id}/expenses?paid_by={g['alice'].id}")
    assert {e["description"] for e in mine.json()["items"]} == {"a1", "a2"}
    assert all(e["paid_by_user_id"] == str(g["alice"].id) for e in mine.json()["items"])

    theirs = await client.get(f"/api/groups/{g['group'].id}/expenses?paid_by={g['bob'].id}")
    assert [e["description"] for e in theirs.json()["items"]] == ["b1"]

    # Unfiltered still returns everything; an id nobody paid under matches none.
    assert len((await client.get(f"/api/groups/{g['group'].id}/expenses")).json()["items"]) == 3
    stranger = await client.get(
        f"/api/groups/{g['group'].id}/expenses?paid_by={uuid.uuid4()}"
    )
    assert stranger.json()["items"] == []


async def test_filter_by_payer_paginates_within_the_filter(client, two_user_group):
    """The filter is applied before limit/offset — a page of Alice's expenses
    must not be diluted by Bob's rows that only the unfiltered query sees."""
    g = two_user_group
    for i in range(3):
        for payer in (g["alice"], g["bob"]):
            await client.post(
                f"/api/groups/{g['group'].id}/expenses",
                json=expense_payload(
                    payer, [g["alice"], g["bob"]], description=f"{payer.email}-{i}"
                ),
                headers=idem(),
            )

    page = await client.get(
        f"/api/groups/{g['group'].id}/expenses?paid_by={g['alice'].id}&limit=2&offset=0"
    )
    rest = await client.get(
        f"/api/groups/{g['group'].id}/expenses?paid_by={g['alice'].id}&limit=2&offset=2"
    )
    assert len(page.json()["items"]) == 2 and len(rest.json()["items"]) == 1
    assert all(
        e["paid_by_user_id"] == str(g["alice"].id)
        for e in page.json()["items"] + rest.json()["items"]
    )


async def test_filter_by_payer_rejects_non_uuid(client, two_user_group):
    g = two_user_group
    r = await client.get(f"/api/groups/{g['group'].id}/expenses?paid_by=not-a-uuid")
    assert r.status_code == 422


async def test_filter_by_payer_still_requires_membership(client, two_user_group, db_session, current_user):
    from conftest import make_user

    g = two_user_group
    outsider = await make_user(db_session, "peeker@test.dev")
    current_user.id = outsider.id
    r = await client.get(f"/api/groups/{g['group'].id}/expenses?paid_by={g['alice'].id}")
    assert r.status_code == 403


async def test_non_member_cannot_touch_expense(client, two_user_group, db_session, current_user):
    from conftest import make_user

    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    assert (await client.get(f"/api/groups/{g['group'].id}/expenses")).status_code == 403
    assert (await client.delete(f"/api/expenses/{created.json()['id']}")).status_code == 403


async def test_unknown_expense_404(client, two_user_group):
    r = await client.delete(f"/api/expenses/{uuid.uuid4()}")
    assert r.status_code == 404


async def test_patch_category_only_leaves_splits_untouched(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}", json={"category": "Climbing"}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == "Climbing"
    # Everything financial is untouched (order of splits is not guaranteed).
    by_user = lambda s: s["user_id"]  # noqa: E731
    assert body["total_amount"] == created.json()["total_amount"]
    assert sorted(body["splits"], key=by_user) == sorted(created.json()["splits"], key=by_user)
    assert body["description"] == created.json()["description"]


async def test_patch_metadata_only_fields(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}",
        json={"description": "Renamed", "expense_date": "2026-05-01"},
    )
    assert r.status_code == 200
    assert r.json()["description"] == "Renamed"
    assert r.json()["expense_date"] == "2026-05-01"
    assert r.json()["splits"] == created.json()["splits"]


async def test_patch_partial_split_fields_rejected(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    # total_amount without the rest of the split group must fail as a unit.
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}", json={"total_amount": "99.00"}
    )
    assert r.status_code == 422
    assert "together" in r.json()["detail"]


async def test_patch_with_split_fields_still_validates_participants(
    client, two_user_group, db_session
):
    from conftest import make_user

    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    stranger = await make_user(db_session, "stranger@test.dev")
    # Full split-field group supplied, but with a non-member participant:
    # the membership validation must still fire behind the new conditional.
    payload = expense_payload(g["alice"], [g["alice"], stranger])
    del payload["description"], payload["category"]
    r = await client.patch(f"/api/expenses/{created.json()['id']}", json=payload)
    assert r.status_code == 400
    assert "members" in r.json()["detail"]


async def test_expense_date_defaults_to_today(client, two_user_group):
    from datetime import date

    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    assert r.json()["expense_date"] == date.today().isoformat()


async def test_expense_date_set_and_modified(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]], expense_date="2026-06-15"),
        headers=idem(),
    )
    assert created.json()["expense_date"] == "2026-06-15"

    edited = await client.patch(
        f"/api/expenses/{created.json()['id']}",
        json=expense_payload(g["alice"], [g["alice"]], expense_date="2026-06-20"),
    )
    assert edited.status_code == 200
    assert edited.json()["expense_date"] == "2026-06-20"


async def test_expenses_ordered_by_occurrence_date(client, two_user_group):
    g = two_user_group
    for d in ("2026-06-10", "2026-06-30", "2026-06-20"):
        await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(g["alice"], [g["alice"]], description=d, expense_date=d),
            headers=idem(),
        )
    listing = await client.get(f"/api/groups/{g['group'].id}/expenses")
    dates = [e["expense_date"] for e in listing.json()["items"]]
    assert dates == ["2026-06-30", "2026-06-20", "2026-06-10"]


class TestDebtCannotOutliveMembership:
    """A member is only removable once their balance is zero — but nothing kept
    it there afterwards. Withdrawing or rewriting an entry they were part of
    moves their net off zero, and they cannot settle it: they are not a member,
    so no expense or settlement may name them. The group would carry the debt
    forever, and could never be deleted either, since that demands every
    balance be zero too.
    """

    async def _settled_and_departed(self, client, g) -> str:
        """Alice pays 30 for both, Bob settles his 15 and leaves. Returns the
        expense id."""
        gid = g["group"].id
        expense = await client.post(
            f"/api/groups/{gid}/expenses",
            json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
            headers=idem(),
        )
        await client.post(
            f"/api/groups/{gid}/settlements",
            json={
                "paid_by_user_id": str(g["bob"].id),
                "paid_to_user_id": str(g["alice"].id),
                "amount": "15.00",
                "currency": "PLN",
            },
            headers=idem(),
        )
        r = await client.delete(f"/api/groups/{gid}/members/{g['bob'].id}")
        assert r.status_code == 204
        return expense.json()["id"]

    async def test_delete_refused_when_it_would_strand_a_former_member(
        self, client, two_user_group
    ):
        g = two_user_group
        expense_id = await self._settled_and_departed(client, g)

        r = await client.delete(f"/api/expenses/{expense_id}")
        assert r.status_code == 400
        assert "no longer in the group" in r.json()["detail"]
        # Refused, not half-applied: the expense is still there.
        listed = await client.get(f"/api/groups/{g['group'].id}/expenses")
        assert [e["id"] for e in listed.json()["items"]] == [expense_id]

    async def test_edit_refused_when_it_would_strand_a_former_member(
        self, client, two_user_group
    ):
        """Splits can only name current members, which is exactly how it
        happens: re-saving the expense drops the departed member's share."""
        g = two_user_group
        expense_id = await self._settled_and_departed(client, g)

        r = await client.patch(
            f"/api/expenses/{expense_id}",
            json=expense_payload(g["alice"], [g["alice"]]),
        )
        assert r.status_code == 400
        assert "no longer in the group" in r.json()["detail"]

    async def test_metadata_edits_still_go_through(self, client, two_user_group):
        """The guard is about money. Fixing a typo moves nobody's balance."""
        g = two_user_group
        expense_id = await self._settled_and_departed(client, g)

        r = await client.patch(f"/api/expenses/{expense_id}", json={"description": "Lunch"})
        assert r.status_code == 200
        assert r.json()["description"] == "Lunch"

    async def test_settlement_delete_is_refused_the_same_way(
        self, client, two_user_group
    ):
        """The mirror image: withdrawing the settlement restores the debt Bob
        cleared on his way out."""
        g = two_user_group
        gid = g["group"].id
        await self._settled_and_departed(client, g)
        settlements = (await client.get(f"/api/groups/{gid}/settlements")).json()

        r = await client.delete(f"/api/settlements/{settlements[0]['id']}")
        assert r.status_code == 400
        assert "no longer in the group" in r.json()["detail"]

    async def test_inviting_the_member_back_is_the_way_out(
        self, client, two_user_group, current_user
    ):
        """Membership is what the guard reads, so a group that has to withdraw
        an entry a departed member was part of brings them back first. This is
        also the only route out for a group already stranded by the deletes
        that used to be allowed."""
        g = two_user_group
        gid = g["group"].id
        expense_id = await self._settled_and_departed(client, g)
        assert (await client.post(
            f"/api/groups/{gid}/invitations", json={"email": "bob@test.dev"}
        )).status_code == 201
        invitation = (await client.get(f"/api/groups/{gid}/invitations")).json()[0]

        current_user.id = g["bob"].id
        assert (await client.post(f"/api/invitations/{invitation['id']}/accept")).status_code == 204

        current_user.id = g["alice"].id
        settlements = (await client.get(f"/api/groups/{gid}/settlements")).json()
        assert (await client.delete(f"/api/expenses/{expense_id}")).status_code == 204
        assert (await client.delete(f"/api/settlements/{settlements[0]['id']}")).status_code == 204
        assert (await client.get(f"/api/groups/{gid}/balances")).json() == {}
