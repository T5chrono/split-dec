"""Settlement lifecycle: create, idempotency, update, soft delete."""

import uuid

from conftest import idem


def settlement_payload(payer, payee, **overrides) -> dict:
    body = {
        "paid_by_user_id": str(payer.id),
        "paid_to_user_id": str(payee.id),
        "amount": "20.00",
        "currency": "PLN",
    }
    body.update(overrides)
    return body


async def test_create_settlement(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=idem(),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == "20.0000"


async def test_create_is_idempotent(client, two_user_group):
    g = two_user_group
    key = idem()
    payload = settlement_payload(g["bob"], g["alice"])
    first = await client.post(
        f"/api/groups/{g['group'].id}/settlements", json=payload, headers=key
    )
    replay = await client.post(
        f"/api/groups/{g['group'].id}/settlements", json=payload, headers=key
    )
    assert first.status_code == 201
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]

    listing = await client.get(f"/api/groups/{g['group'].id}/settlements")
    assert len(listing.json()) == 1  # replay did not create a second row


async def test_payer_equals_payee_rejected(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["bob"]),
        headers=idem(),
    )
    assert r.status_code == 422


async def test_non_member_party_rejected(client, two_user_group, db_session):
    from conftest import make_user

    g = two_user_group
    stranger = await make_user(db_session, "stranger@test.dev")
    r = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], stranger),
        headers=idem(),
    )
    assert r.status_code == 400


async def test_amount_precision_validated(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"], amount="20.001"),
        headers=idem(),
    )
    assert r.status_code == 422


async def test_idempotency_replay_is_scoped_to_the_group(
    client, two_user_group, db_session
):
    """A key used in another group must 409, never return that group's record."""
    from conftest import make_group

    g = two_user_group
    key = idem()
    first = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=key,
    )
    assert first.status_code == 201

    other = await make_group(db_session, g["alice"], g["bob"], name="Other")
    r = await client.post(
        f"/api/groups/{other.id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=key,  # same Idempotency-Key, different group
    )
    assert r.status_code == 409
    assert "Idempotency-Key" in r.json()["detail"]


async def test_update_settlement(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=idem(),
    )
    r = await client.put(
        f"/api/settlements/{created.json()['id']}", json={"amount": "35.00"}
    )
    assert r.status_code == 200
    assert r.json()["amount"] == "35.0000"
    # Unchanged fields survive a partial update.
    assert r.json()["paid_by_user_id"] == str(g["bob"].id)


async def test_update_cannot_make_payer_equal_payee(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=idem(),
    )
    r = await client.put(
        f"/api/settlements/{created.json()['id']}",
        json={"paid_by_user_id": str(g["alice"].id)},
    )
    assert r.status_code == 422


async def test_soft_delete(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/settlements",
        json=settlement_payload(g["bob"], g["alice"]),
        headers=idem(),
    )
    sid = created.json()["id"]
    assert (await client.delete(f"/api/settlements/{sid}")).status_code == 204
    assert (await client.get(f"/api/groups/{g['group'].id}/settlements")).json() == []
    assert (await client.delete(f"/api/settlements/{sid}")).status_code == 404


async def test_unknown_settlement_404(client, two_user_group):
    assert (await client.put(
        f"/api/settlements/{uuid.uuid4()}", json={"amount": "5.00"}
    )).status_code == 404
