"""Group invitations: invite, accept/decline, cancel, invite-by-email signup flow."""

import uuid

import pytest
from conftest import make_group, make_user

from _src.models import GroupInvitation
from _src.routers import invitations as invitations_router


async def _invite(client, group_id, email):
    return await client.post(f"/api/groups/{group_id}/invitations", json={"email": email})


async def test_invite_existing_user_requires_acceptance(
    client, db_session, two_user_group, current_user
):
    g = two_user_group
    carol = await make_user(db_session, "carol@test.dev", "Carol")

    r = await _invite(client, g["group"].id, "Carol@test.dev")  # case-insensitive
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "PENDING"

    # Not a member yet — must accept first.
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert len(detail.json()["members"]) == 2

    # Carol sees the invitation and accepts.
    current_user.id = carol.id
    mine = (await client.get("/api/invitations/mine")).json()
    assert len(mine) == 1
    assert mine[0]["group_name"] == g["group"].name
    assert mine[0]["invited_by_name"] == "Alice"

    assert (await client.post(f"/api/invitations/{mine[0]['id']}/accept")).status_code == 204
    assert (await client.get("/api/invitations/mine")).json() == []
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert len(detail.json()["members"]) == 3


async def test_decline_invitation(client, db_session, two_user_group, current_user):
    g = two_user_group
    carol = await make_user(db_session, "carol@test.dev", "Carol")
    inv = (await _invite(client, g["group"].id, "carol@test.dev")).json()

    current_user.id = carol.id
    assert (await client.post(f"/api/invitations/{inv['id']}/decline")).status_code == 204
    assert (await client.get("/api/invitations/mine")).json() == []

    current_user.id = g["alice"].id
    detail = await client.get(f"/api/groups/{g['group'].id}")
    assert len(detail.json()["members"]) == 2
    # Declined invitation no longer listed as pending for the group.
    assert (await client.get(f"/api/groups/{g['group'].id}/invitations")).json() == []


async def test_only_invitee_can_respond(client, db_session, two_user_group, current_user):
    g = two_user_group
    await make_user(db_session, "carol@test.dev", "Carol")
    inv = (await _invite(client, g["group"].id, "carol@test.dev")).json()

    # Alice (the inviter) cannot accept on Carol's behalf.
    assert (await client.post(f"/api/invitations/{inv['id']}/accept")).status_code == 403


async def test_invite_already_member_rejected(client, two_user_group):
    g = two_user_group
    r = await _invite(client, g["group"].id, "bob@test.dev")
    assert r.status_code == 400


async def test_duplicate_pending_invite_returns_existing(client, db_session, two_user_group):
    g = two_user_group
    await make_user(db_session, "carol@test.dev", "Carol")
    first = await _invite(client, g["group"].id, "carol@test.dev")
    replay = await _invite(client, g["group"].id, "carol@test.dev")
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]


async def test_cancel_invitation(client, db_session, two_user_group):
    g = two_user_group
    await make_user(db_session, "carol@test.dev", "Carol")
    inv = (await _invite(client, g["group"].id, "carol@test.dev")).json()

    assert (await client.delete(f"/api/invitations/{inv['id']}")).status_code == 204
    assert (await client.get(f"/api/groups/{g['group'].id}/invitations")).json() == []


async def test_cancelled_invitation_is_kept_and_address_can_be_reinvited(
    client, db_session, two_user_group
):
    g = two_user_group
    inv = (await _invite(client, g["group"].id, "carol@test.dev")).json()
    await client.delete(f"/api/invitations/{inv['id']}")

    # Retained (it still counts against the send quotas) but no longer live.
    async with db_session() as s:
        row = await s.get(GroupInvitation, uuid.UUID(inv["id"]))
        assert row is not None and row.status == "CANCELLED"

    again = await _invite(client, g["group"].id, "carol@test.dev")
    assert again.status_code == 201
    assert again.json()["id"] != inv["id"]


async def test_invite_unknown_email_recorded_without_email_provider(client, two_user_group):
    g = two_user_group
    r = await _invite(client, g["group"].id, "future.user@test.dev")
    assert r.status_code == 201

    pending = (await client.get(f"/api/groups/{g['group'].id}/invitations")).json()
    assert [p["email"] for p in pending] == ["future.user@test.dev"]


async def test_invitee_who_signs_up_later_sees_invitation(
    client, db_session, two_user_group, current_user
):
    g = two_user_group
    await _invite(client, g["group"].id, "future.user@test.dev")

    # The person signs up later with the invited email.
    newcomer = await make_user(db_session, "future.user@test.dev", "Future")
    current_user.id = newcomer.id
    mine = (await client.get("/api/invitations/mine")).json()
    assert len(mine) == 1

    assert (await client.post(f"/api/invitations/{mine[0]['id']}/accept")).status_code == 204
    groups = (await client.get("/api/groups")).json()
    assert [x["id"] for x in groups] == [str(g["group"].id)]


async def test_invite_requires_membership(client, db_session, two_user_group, current_user):
    outsider = await make_user(db_session, "outsider@test.dev")
    current_user.id = outsider.id
    r = await _invite(client, two_user_group["group"].id, "carol@test.dev")
    assert r.status_code == 403


async def test_invalid_email_rejected(client, two_user_group):
    r = await _invite(client, two_user_group["group"].id, "not-an-email")
    assert r.status_code == 422


async def test_respond_to_unknown_invitation_404(client, two_user_group):
    assert (
        await client.post(f"/api/invitations/{uuid.uuid4()}/accept")
    ).status_code == 404


class TestNoRegistrationOracle:
    """Anyone can create a group and invite arbitrary addresses, so nothing
    the endpoint returns may reveal whether an address has an account."""

    async def test_response_identical_for_registered_and_unregistered(
        self, client, db_session, two_user_group
    ):
        g = two_user_group
        await make_user(db_session, "registered@test.dev", "Carol")
        # Separate groups so the two invitations cannot collide.
        other = await make_group(db_session, g["alice"], name="Other")

        known = await _invite(client, g["group"].id, "registered@test.dev")
        unknown = await _invite(client, other.id, "nobody@test.dev")

        assert known.status_code == unknown.status_code == 201
        a, b = known.json(), unknown.json()
        assert a.keys() == b.keys()
        # Everything except the row's own identity and the echoed address.
        assert {k: v for k, v in a.items() if k not in ("id", "email", "group_id")} == {
            k: v for k, v in b.items() if k not in ("id", "email", "group_id")
        }
        assert "user_exists" not in a
        assert "email_sent" not in a
        assert "invited_user_id" not in a

    async def test_pending_list_hides_invited_user_id(self, client, db_session, two_user_group):
        g = two_user_group
        await make_user(db_session, "registered@test.dev", "Carol")
        await _invite(client, g["group"].id, "registered@test.dev")
        pending = (await client.get(f"/api/groups/{g['group'].id}/invitations")).json()
        assert "invited_user_id" not in pending[0]


class TestRateLimits:
    """Invitations to non-members send mail, and cancelling frees the slot —
    so the quotas, not the unique index, are what bound outbound volume."""

    @pytest.fixture(autouse=True)
    def _small_quotas(self, monkeypatch):
        monkeypatch.setattr(invitations_router, "INVITE_MAX_PER_INVITER", 5)
        monkeypatch.setattr(invitations_router, "INVITE_MAX_PER_RECIPIENT", 2)
        monkeypatch.setattr(invitations_router, "INVITE_MAX_GLOBAL", 50)

    async def test_invite_cancel_loop_cannot_spam_one_address(self, client, two_user_group):
        g = two_user_group
        for _ in range(2):
            inv = await _invite(client, g["group"].id, "victim@test.dev")
            assert inv.status_code == 201
            assert (await client.delete(f"/api/invitations/{inv.json()['id']}")).status_code == 204

        blocked = await _invite(client, g["group"].id, "victim@test.dev")
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        # The message must not say which of the three limits was hit.
        assert "victim@test.dev" not in blocked.json()["detail"]

    async def test_per_inviter_limit_spans_groups(self, client, db_session, two_user_group):
        g = two_user_group
        groups = [g["group"]] + [
            await make_group(db_session, g["alice"], name=f"G{i}") for i in range(5)
        ]
        sent = 0
        for i, grp in enumerate(groups):
            r = await _invite(client, grp.id, f"person{i}@test.dev")
            if r.status_code == 429:
                break
            assert r.status_code == 201
            sent += 1
        assert sent == 5  # INVITE_MAX_PER_INVITER

    async def test_replaying_a_pending_invite_costs_no_quota(self, client, two_user_group):
        g = two_user_group
        first = await _invite(client, g["group"].id, "carol@test.dev")
        assert first.status_code == 201
        for _ in range(5):
            replay = await _invite(client, g["group"].id, "carol@test.dev")
            assert replay.status_code == 200
            assert replay.json()["id"] == first.json()["id"]