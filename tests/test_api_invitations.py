"""Group invitations: invite, accept/decline, cancel, invite-by-email signup flow."""

import uuid

from conftest import make_user


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
    assert body["user_exists"] is True
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


async def test_invite_unknown_email_recorded_without_email_provider(client, two_user_group):
    g = two_user_group
    r = await _invite(client, g["group"].id, "future.user@test.dev")
    assert r.status_code == 201
    body = r.json()
    assert body["user_exists"] is False
    assert body["email_sent"] is False  # no RESEND_API_KEY in tests

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