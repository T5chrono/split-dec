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
