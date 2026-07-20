"""Account deletion (the search endpoint was removed on security review)."""

import uuid

from sqlalchemy import select, text

from conftest import expense_payload, idem, make_group, make_user
from _src.models import GroupInvitation, GroupMember, User


async def test_search_endpoint_removed(client, two_user_group):
    # Removed: it let any authenticated caller probe whether an email is
    # registered and fetch the profile. Invitations cover the use case.
    r = await client.get("/api/users/search?email=bob@test.dev")
    assert r.status_code == 404


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


async def test_deleted_account_token_cannot_act(client, two_user_group, current_user):
    """A JWT issued before deletion stays cryptographically valid until it
    expires; endpoints not gated by membership must reject it explicitly."""
    g = two_user_group
    assert (await client.delete("/api/users/me")).status_code == 204

    # Same caller id (same token) after deletion:
    assert (await client.post("/api/groups", json={"name": "Zombie"})).status_code == 401
    assert (await client.get("/api/invitations/mine")).status_code == 401
    assert (await client.delete("/api/users/me")).status_code == 401
    # Membership-gated endpoints are already safe (memberships were removed).
    assert (await client.get(f"/api/groups/{g['group'].id}")).status_code == 403


async def test_delete_account_drops_pending_invitations_addressed_to_it(
    client, db_session, two_user_group, current_user
):
    """A pending invitation is an unexpiring capability matched by email, so
    it must not survive to be inherited by the next holder of the address."""
    g = two_user_group
    carol = await make_user(db_session, "carol@test.dev", "Carol")
    await client.post(
        f"/api/groups/{g['group'].id}/invitations", json={"email": "carol@test.dev"}
    )

    current_user.id = carol.id
    assert len((await client.get("/api/invitations/mine")).json()) == 1
    assert (await client.delete("/api/users/me")).status_code == 204

    async with db_session() as s:
        rows = (await s.execute(select(GroupInvitation))).scalars().all()
        assert rows == []

    # Someone who registers carol@test.dev later starts with a clean slate.
    reused = await make_user(db_session, "carol@test.dev", "Different Carol")
    current_user.id = reused.id
    assert (await client.get("/api/invitations/mine")).json() == []


async def test_delete_account_anonymizes_answered_invitations(
    client, db_session, two_user_group, current_user
):
    g = two_user_group
    carol = await make_user(db_session, "carol@test.dev", "Carol")
    inv = (
        await client.post(
            f"/api/groups/{g['group'].id}/invitations", json={"email": "carol@test.dev"}
        )
    ).json()

    current_user.id = carol.id
    assert (await client.post(f"/api/invitations/{inv['id']}/decline")).status_code == 204
    assert (await client.delete("/api/users/me")).status_code == 204

    async with db_session() as s:
        row = await s.get(GroupInvitation, uuid.UUID(inv["id"]))
        assert row.status == "DECLINED"  # history kept for the group
        assert row.email == f"deleted-{carol.id}@users.splitdec.invalid"


async def test_delete_account_removes_invitations_across_groups(
    client, db_session, two_user_group, current_user
):
    g = two_user_group
    dave = await make_user(db_session, "dave@test.dev", "Dave")
    other = await make_group(db_session, g["bob"], name="Other")
    for group_id in (g["group"].id, other.id):
        current_user.id = g["alice"].id if group_id == g["group"].id else g["bob"].id
        await client.post(
            f"/api/groups/{group_id}/invitations", json={"email": "dave@test.dev"}
        )

    current_user.id = dave.id
    assert (await client.delete("/api/users/me")).status_code == 204
    async with db_session() as s:
        assert (await s.execute(select(GroupInvitation))).scalars().all() == []


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
