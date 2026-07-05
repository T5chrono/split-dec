"""Groups, membership, and the balances endpoint."""

import uuid

from conftest import expense_payload, idem, make_user


async def test_create_group_adds_creator_as_member(client, db_session, current_user):
    alice = await make_user(db_session, "alice@test.dev", "Alice")
    current_user.id = alice.id

    r = await client.post("/api/groups", json={"name": "Ski trip"})
    assert r.status_code == 201
    group_id = r.json()["id"]

    detail = await client.get(f"/api/groups/{group_id}")
    assert detail.status_code == 200
    members = detail.json()["members"]
    assert [m["id"] for m in members] == [str(alice.id)]


async def test_list_only_my_groups(client, db_session, current_user, two_user_group):
    carol = await make_user(db_session, "carol@test.dev")
    current_user.id = carol.id
    assert (await client.get("/api/groups")).json() == []

    current_user.id = two_user_group["alice"].id
    groups = (await client.get("/api/groups")).json()
    assert [g["id"] for g in groups] == [str(two_user_group["group"].id)]


async def test_group_detail_403_for_non_member(client, db_session, current_user, two_user_group):
    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    assert (await client.get(f"/api/groups/{two_user_group['group'].id}")).status_code == 403


async def test_group_404(client, two_user_group):
    assert (await client.get(f"/api/groups/{uuid.uuid4()}")).status_code == 404


async def test_remove_member_blocked_by_balance_in_any_currency(client, two_user_group):
    g = two_user_group
    # Bob owes Alice 15 PLN...
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    # ...and is owed 5 EUR — both currencies must block removal.
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(
            g["bob"], [g["alice"]], total_amount="5.00", currency="EUR",
            splits=[{"user_id": str(g["alice"].id)}],
        ),
        headers=idem(),
    )
    r = await client.delete(f"/api/groups/{g['group'].id}/members/{g['bob'].id}")
    assert r.status_code == 400
    assert "EUR" in r.json()["detail"] and "PLN" in r.json()["detail"]


async def test_remove_member_after_settling(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json={
            "paid_by_user_id": str(g["bob"].id),
            "paid_to_user_id": str(g["alice"].id),
            "amount": "15.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    r = await client.delete(f"/api/groups/{g['group'].id}/members/{g['bob'].id}")
    assert r.status_code == 204


async def test_delete_empty_group(client, two_user_group):
    g = two_user_group
    assert (await client.delete(f"/api/groups/{g['group'].id}")).status_code == 204
    assert (await client.get("/api/groups")).json() == []
    assert (await client.get(f"/api/groups/{g['group'].id}")).status_code == 404


async def test_delete_settled_group_removes_all_records(client, two_user_group, db_session):
    g = two_user_group
    # Expense then a settlement that clears it -> group is settled but has records.
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]], total_amount="20.00"),
        headers=idem(),
    )
    await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json={
            "paid_by_user_id": str(g["bob"].id),
            "paid_to_user_id": str(g["alice"].id),
            "amount": "10.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    assert (await client.delete(f"/api/groups/{g['group'].id}")).status_code == 204

    # Child rows are gone too (no orphans).
    from sqlalchemy import func, select
    from _src.models import Expense, ExpenseSplit, GroupMember, Settlement

    async with db_session() as s:
        for model in (Expense, ExpenseSplit, GroupMember, Settlement):
            count = (await s.execute(select(func.count()).select_from(model))).scalar_one()
            assert count == 0, model.__name__


async def test_delete_unsettled_group_blocked(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.delete(f"/api/groups/{g['group'].id}")
    assert r.status_code == 400
    assert "PLN" in r.json()["detail"]
    # Still there.
    assert (await client.get(f"/api/groups/{g['group'].id}")).status_code == 200


async def test_delete_group_requires_membership(client, two_user_group, db_session, current_user):
    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    assert (
        await client.delete(f"/api/groups/{two_user_group['group'].id}")
    ).status_code == 403


async def test_balances_shape_and_math(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]], total_amount="90.00"),
        headers=idem(),
    )
    r = await client.get(f"/api/groups/{g['group'].id}/balances")
    assert r.status_code == 200
    assert r.json() == {
        "PLN": [
            {
                "from_user_id": str(g["bob"].id),
                "to_user_id": str(g["alice"].id),
                "amount": "45.0000",
            }
        ]
    }


async def test_balances_include_settlements_and_soft_deletes(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]], total_amount="90.00"),
        headers=idem(),
    )
    # Partial settlement reduces the debt.
    s = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json={
            "paid_by_user_id": str(g["bob"].id),
            "paid_to_user_id": str(g["alice"].id),
            "amount": "20.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    r = await client.get(f"/api/groups/{g['group'].id}/balances")
    assert r.json()["PLN"][0]["amount"] == "25.0000"

    # Deleting the settlement restores the full debt (independent soft-delete filter).
    await client.delete(f"/api/settlements/{s.json()['id']}")
    r = await client.get(f"/api/groups/{g['group'].id}/balances")
    assert r.json()["PLN"][0]["amount"] == "45.0000"
