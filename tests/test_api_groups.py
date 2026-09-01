"""Groups, membership, and the balances endpoint."""

import uuid

from sqlalchemy import select

from conftest import expense_payload, idem, make_user
from _src.models import Expense, Group, GroupInvitation, User


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


async def test_last_member_cannot_leave_the_group_standing(client, two_user_group):
    """Every route into a group is membership-gated, so a group with no members
    could never be read, settled or deleted again by anyone. Deleting the group
    is the gesture that was meant."""
    g = two_user_group
    gid = g["group"].id
    assert (await client.delete(f"/api/groups/{gid}/members/{g['bob'].id}")).status_code == 204

    r = await client.delete(f"/api/groups/{gid}/members/{g['alice'].id}")
    assert r.status_code == 400
    assert "last member" in r.json()["detail"]
    # And the group is still hers to use, not half-dismantled.
    assert (await client.get(f"/api/groups/{gid}")).status_code == 200
    assert (await client.delete(f"/api/groups/{gid}")).status_code == 204


async def test_deleting_the_last_account_takes_the_group_with_it(
    client, db_session, two_user_group
):
    """The same invariant where nobody is left to ask: account deletion cannot
    be refused on the group's behalf, so the emptied group goes too."""
    g = two_user_group
    gid = g["group"].id
    await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    assert (await client.delete(f"/api/groups/{gid}/members/{g['bob'].id}")).status_code == 204

    assert (await client.delete("/api/users/me")).status_code == 204

    async with db_session() as s:
        assert await s.get(Group, gid) is None
        assert (
            await s.execute(select(Expense).where(Expense.group_id == gid))
        ).scalars().all() == []


async def test_deleting_an_account_leaves_groups_that_still_have_members(
    client, db_session, two_user_group
):
    g = two_user_group
    assert (await client.delete("/api/users/me")).status_code == 204
    async with db_session() as s:
        assert await s.get(Group, g["group"].id) is not None


async def test_rename_group(client, two_user_group):
    g = two_user_group
    r = await client.patch(f"/api/groups/{g['group'].id}", json={"name": "New name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New name"
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert detail.json()["name"] == "New name"


async def test_rename_group_requires_membership(
    client, db_session, two_user_group, current_user
):
    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    r = await client.patch(
        f"/api/groups/{two_user_group['group'].id}", json={"name": "Hijacked"}
    )
    assert r.status_code == 403


async def test_rename_group_validates_name(client, two_user_group):
    r = await client.patch(f"/api/groups/{two_user_group['group'].id}", json={"name": ""})
    assert r.status_code == 422


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
    # A pending invitation should be swept away too.
    await client.post(
        f"/api/groups/{g['group'].id}/invitations",
        json={"email": "future@test.dev"},
    )

    assert (await client.delete(f"/api/groups/{g['group'].id}")).status_code == 204

    # Every child row is gone too (no orphans), including invitations and the group.
    from sqlalchemy import func, select
    from _src.models import (
        Expense,
        ExpenseSplit,
        Group,
        GroupInvitation,
        GroupMember,
        Settlement,
    )

    async with db_session() as s:
        for model in (
            Expense,
            ExpenseSplit,
            GroupMember,
            Settlement,
            GroupInvitation,
            Group,
        ):
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


async def test_delete_unsettled_group_blocked_multi_currency(client, two_user_group):
    g = two_user_group
    for currency in ("PLN", "EUR"):
        await client.post(
            f"/api/groups/{g['group'].id}/expenses",
            json=expense_payload(
                g["alice"], [g["alice"], g["bob"]], total_amount="10.00", currency=currency
            ),
            headers=idem(),
        )
    r = await client.delete(f"/api/groups/{g['group'].id}")
    assert r.status_code == 400
    # Every unsettled currency is named, not just one.
    assert "PLN" in r.json()["detail"] and "EUR" in r.json()["detail"]


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


async def test_totals_per_currency_ignore_settlements_and_soft_deletes(
    client, two_user_group
):
    g = two_user_group
    gid = g["group"].id
    assert (await client.get(f"/api/groups/{gid}/totals")).json() == []

    e = await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]], total_amount="90.00"),
        headers=idem(),
    )
    await client.post(
        f"/api/groups/{gid}/expenses",
        json=expense_payload(
            g["bob"], [g["alice"]], total_amount="5.00", currency="EUR",
            splits=[{"user_id": str(g["alice"].id)}],
        ),
        headers=idem(),
    )
    # Moving money between members is not spending.
    await client.post(
        f"/api/groups/{gid}/settlements",
        json={
            "paid_by_user_id": str(g["bob"].id),
            "paid_to_user_id": str(g["alice"].id),
            "amount": "20.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    assert (await client.get(f"/api/groups/{gid}/totals")).json() == [
        {"currency": "EUR", "total": "5.0000"},
        {"currency": "PLN", "total": "90.0000"},
    ]

    await client.delete(f"/api/expenses/{e.json()['id']}")
    assert (await client.get(f"/api/groups/{gid}/totals")).json() == [
        {"currency": "EUR", "total": "5.0000"},
    ]


async def test_totals_403_for_non_member(client, db_session, current_user, two_user_group):
    outsider = await make_user(db_session, "totals-outsider@test.dev")
    current_user.id = outsider.id
    r = await client.get(f"/api/groups/{two_user_group['group'].id}/totals")
    assert r.status_code == 403


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


async def test_removing_a_member_revokes_their_pending_invitations(
    client, db_session, two_user_group, current_user
):
    """A removed member must not be able to walk back in on an invitation that
    outlived their membership.

    Reachable because one person can hold two live invitations to one group:
    uq_group_invitations_pending is keyed on (group_id, email), so an address
    change leaves the invitation sent to the old address PENDING while they
    join through the new one.
    """
    g = two_user_group
    gid = g["group"].id
    carol = await make_user(db_session, "carol-old@test.dev", "Carol")

    stale = (
        await client.post(
            f"/api/groups/{gid}/invitations", json={"email": "carol-old@test.dev"}
        )
    ).json()

    # Carol changes her address in Supabase Auth; handle_user_updated mirrors it
    # into public.users (migration 20260827000100).
    async with db_session() as s:
        row = await s.get(User, carol.id)
        row.email = "carol-new@test.dev"
        await s.commit()

    fresh = (
        await client.post(
            f"/api/groups/{gid}/invitations", json={"email": "carol-new@test.dev"}
        )
    ).json()
    assert fresh["id"] != stale["id"]

    current_user.id = carol.id
    assert (await client.post(f"/api/invitations/{fresh['id']}/accept")).status_code == 204

    current_user.id = g["alice"].id
    assert (await client.delete(f"/api/groups/{gid}/members/{carol.id}")).status_code == 204

    # The stale invitation is spent, not merely unused: it is gone from her list
    # and no longer answerable.
    current_user.id = carol.id
    assert (await client.get("/api/invitations/mine")).json() == []
    assert (await client.post(f"/api/invitations/{stale['id']}/accept")).status_code == 404

    current_user.id = g["alice"].id
    detail = await client.get(f"/api/groups/{gid}")
    assert {m["id"] for m in detail.json()["members"]} == {
        str(g["alice"].id),
        str(g["bob"].id),
    }

    # CANCELLED rather than deleted, like cancel_invitation: the group keeps its
    # record, and the partial unique index covers only PENDING rows, so removal
    # is not a ban — she can be invited back.
    async with db_session() as s:
        assert (await s.get(GroupInvitation, uuid.UUID(stale["id"]))).status == "CANCELLED"
    assert (
        await client.post(
            f"/api/groups/{gid}/invitations", json={"email": "carol-new@test.dev"}
        )
    ).status_code == 201


async def test_removal_revokes_an_invitation_with_no_invited_user_id(
    client, db_session, two_user_group
):
    """The other half of the match. An invitation created before the invitee had
    an account carries a NULL invited_user_id and is findable only by address,
    so removal matches on both columns — the pair delete_account already uses.
    Inserted directly: the invite endpoint refuses an address that is already a
    member, which is exactly why only a regression test holds this branch open.
    """
    g = two_user_group
    gid = g["group"].id
    async with db_session() as s:
        s.add(
            GroupInvitation(
                group_id=gid,
                email="bob@test.dev",
                invited_by=g["alice"].id,
                invited_user_id=None,
            )
        )
        await s.commit()

    assert (await client.delete(f"/api/groups/{gid}/members/{g['bob'].id}")).status_code == 204

    async with db_session() as s:
        inv = (await s.execute(select(GroupInvitation))).scalars().one()
        assert inv.status == "CANCELLED"
        assert inv.responded_at is not None
