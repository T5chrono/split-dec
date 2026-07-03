"""User search and account deletion."""

from sqlalchemy import select, text

from conftest import expense_payload, idem, make_user
from _src.models import GroupMember, User


async def test_search_case_insensitive(client, two_user_group):
    r = await client.get("/api/users/search?email=BOB@test.dev")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(two_user_group["bob"].id)
    assert set(body) == {"id", "full_name", "avatar_url"}  # no email leak


async def test_search_no_match_404(client, two_user_group):
    assert (await client.get("/api/users/search?email=nobody@test.dev")).status_code == 404


async def test_delete_account_blocked_with_outstanding_balance(client, two_user_group):
    g = two_user_group
    await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"], g["bob"]]),
        headers=idem(),
    )
    r = await client.delete("/api/users/me")
    assert r.status_code == 400
    assert "PLN" in r.json()["detail"]


async def test_delete_account_succeeds_when_settled(client, two_user_group, db_session):
    g = two_user_group
    alice_id = g["alice"].id

    r = await client.delete("/api/users/me")
    assert r.status_code == 204

    async with db_session() as s:
        # Left all groups.
        memberships = (
            await s.execute(select(GroupMember).where(GroupMember.user_id == alice_id))
        ).scalars().all()
        assert memberships == []
        # PII scrubbed but ledger identity kept.
        user = await s.get(User, alice_id)
        assert user is not None
        assert user.full_name == "Deleted user"
        assert user.avatar_url is None
        assert user.email == f"deleted-{alice_id}@users.splitdec.invalid"
        # Sign-in revoked: auth.users row removed.
        remaining = (
            await s.execute(
                text("SELECT COUNT(*) FROM auth.users WHERE id = :id"),
                {"id": str(alice_id)},
            )
        ).scalar_one()
        assert remaining == 0


async def test_delete_account_keeps_history_for_others(client, two_user_group, current_user):
    g = two_user_group
    # Alice pays for a shared dinner, Bob settles his half, then Alice leaves.
    created = await client.post(
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
    assert (await client.delete("/api/users/me")).status_code == 204

    # Bob still sees the expense history and a settled group.
    current_user.id = g["bob"].id
    listing = await client.get(f"/api/groups/{g['group'].id}/expenses")
    assert listing.json()["items"][0]["id"] == created.json()["id"]
    balances = await client.get(f"/api/groups/{g['group'].id}/balances")
    assert all(v == [] for v in balances.json().values())
