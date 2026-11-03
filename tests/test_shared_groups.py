"""Shared-budget groups (groups.mode = 'SHARED'): every expense is the payer's
own, nothing is ever owed, and nothing can be settled."""

from conftest import expense_payload, idem, make_group


def _settlement(payer, payee, amount="10.00") -> dict:
    return {
        "paid_by_user_id": str(payer.id),
        "paid_to_user_id": str(payee.id),
        "amount": amount,
        "currency": "PLN",
    }


async def _owed(client, group_id) -> dict:
    """Balances as {currency: [transfers]}, with empty buckets dropped."""
    r = await client.get(f"/api/groups/{group_id}/balances")
    assert r.status_code == 200, r.text
    return {c: t for c, t in r.json().items() if t}


async def _make_shared(client, group_id):
    r = await client.patch(f"/api/groups/{group_id}", json={"mode": "SHARED"})
    assert r.status_code == 200, r.text
    return r


async def test_groups_default_to_split(client, two_user_group):
    g = two_user_group
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert detail.json()["mode"] == "SPLIT"
    created = await client.post("/api/groups", json={"name": "Trip"})
    assert created.json()["mode"] == "SPLIT"


async def test_create_shared_group(client, two_user_group):
    created = await client.post("/api/groups", json={"name": "Home", "mode": "SHARED"})
    assert created.status_code == 201, created.text
    assert created.json()["mode"] == "SHARED"
    listed = await client.get("/api/groups")
    assert {g["name"]: g["mode"] for g in listed.json()}["Home"] == "SHARED"


async def test_unknown_mode_rejected(client, two_user_group):
    r = await client.post("/api/groups", json={"name": "Home", "mode": "POOL"})
    assert r.status_code == 422
    r = await client.patch(
        f"/api/groups/{two_user_group['group'].id}", json={"mode": "POOL"}
    )
    assert r.status_code == 422


async def test_expense_in_shared_group_is_the_payers_alone(client, two_user_group):
    """An equal split sent by the client is recorded payer-only, so the group
    total grows and nobody owes anybody."""
    g = two_user_group
    await _make_shared(client, g["group"].id)
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["bob"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["split_type"] == "EXACT"
    assert body["paid_by_user_id"] == str(g["bob"].id)
    assert body["splits"] == [{"user_id": str(g["bob"].id), "owed_amount": "30.0000"}]
    assert await _owed(client, g["group"].id) == {}
    totals = await client.get(f"/api/groups/{g['group'].id}/totals")
    assert totals.json() == [{"currency": "PLN", "total": "30.0000"}]


async def test_shared_split_ignores_participants_who_are_not_members(
    client, two_user_group, db_session
):
    """The forced split replaces the client's list before validation, so what
    it named no longer matters — only the payer has to be a member."""
    from conftest import make_user

    g = two_user_group
    stranger = await make_user(db_session, "stranger@test.dev")
    await _make_shared(client, g["group"].id)
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], stranger]),
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(stranger, [g["alice"]]),
        headers=idem(),
    )
    assert r.status_code == 400


async def test_financial_edit_in_shared_group_stays_payer_only(client, two_user_group):
    g = two_user_group
    await _make_shared(client, g["group"].id)
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}",
        json=expense_payload(g["bob"], [g["alice"], g["bob"]], total_amount="50.00"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["splits"] == [{"user_id": str(g["bob"].id), "owed_amount": "50.0000"}]
    assert await _owed(client, g["group"].id) == {}


async def test_settlement_refused_in_shared_group(client, two_user_group):
    g = two_user_group
    await _make_shared(client, g["group"].id)
    r = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=_settlement(g["bob"], g["alice"]),
        headers=idem(),
    )
    assert r.status_code == 400
    assert "shared budget" in r.json()["detail"]


async def test_cannot_make_unsettled_group_shared(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.patch(f"/api/groups/{g['group'].id}", json={"mode": "SHARED"})
    assert r.status_code == 400
    assert "PLN" in r.json()["detail"]
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert detail.json()["mode"] == "SPLIT"


async def test_refused_mode_change_does_not_rename(client, two_user_group):
    """Both fields in one request are all-or-nothing."""
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/groups/{g['group'].id}", json={"name": "Home", "mode": "SHARED"}
    )
    assert r.status_code == 400
    assert (await client.get(f"/api/groups/{g['group'].id}")).json()["name"] == "Trip"


async def test_settled_history_survives_the_switch(client, two_user_group):
    """A split expense paid off by a settlement nets to zero, so the group can
    become shared — but withdrawing either row afterwards would reopen a debt
    the shared group has no way to settle, and is refused."""
    g = two_user_group
    gid = g["group"].id
    expense = await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    settlement = await client.post(
        f"/api/groups/{gid}/settlements",
        json=_settlement(g["bob"], g["alice"], amount="15.00"),
        headers=idem(),
    )
    assert settlement.status_code == 201, settlement.text
    await _make_shared(client, gid)

    r = await client.delete(f"/api/expenses/{expense.json()['id']}")
    assert r.status_code == 400
    assert "shared budget" in r.json()["detail"]
    r = await client.delete(f"/api/settlements/{settlement.json()['id']}")
    assert r.status_code == 400
    # Un-splitting the old expense moves Bob's 15 PLN as surely as deleting it.
    r = await client.patch(
        f"/api/expenses/{expense.json()['id']}",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
    )
    assert r.status_code == 400

    # Metadata never moves money, so it stays editable.
    r = await client.patch(
        f"/api/expenses/{expense.json()['id']}", json={"description": "Dinner out"}
    )
    assert r.status_code == 200, r.text
    assert await _owed(client, gid) == {}


async def test_shared_group_can_switch_back(client, two_user_group):
    g = two_user_group
    gid = g["group"].id
    await _make_shared(client, gid)
    await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.patch(f"/api/groups/{gid}", json={"mode": "SPLIT"})
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "SPLIT"
    # Splits again from here on; the earlier row keeps its payer-only split.
    await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    owed = await _owed(client, gid)
    assert owed == {
        "PLN": [
            {
                "from_user_id": str(g["bob"].id),
                "to_user_id": str(g["alice"].id),
                "amount": "15.0000",
            }
        ]
    }


async def test_mode_change_requires_membership(client, db_session, two_user_group, current_user):
    from conftest import make_user

    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    r = await client.patch(
        f"/api/groups/{two_user_group['group'].id}", json={"mode": "SHARED"}
    )
    assert r.status_code == 403


async def test_shared_group_can_be_deleted_and_left(client, two_user_group, db_session):
    """Its balances are always zero, so the zero-balance gates never refuse."""
    g = two_user_group
    gid = g["group"].id
    await _make_shared(client, gid)
    await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["bob"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    assert (await client.delete(f"/api/groups/{gid}/members/{g['bob'].id}")).status_code == 204

    other = await make_group(db_session, g["alice"], g["bob"], name="Home")
    await _make_shared(client, other.id)
    await client.post(
        f"/api/groups/{other.id}/expenses",
        json=expense_payload(g["bob"], [g["alice"]]),
        headers=idem(),
    )
    assert (await client.delete(f"/api/groups/{other.id}")).status_code == 204
