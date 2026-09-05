"""The seeded welcome group (api/_src/welcome.py)."""

import uuid

from sqlalchemy import func, select

from conftest import idem, make_user
from _src.models import Expense, Group, GroupMember, User
from _src.welcome import SYSTEM_USER_ID, WELCOME_TEXT


async def seed(client, lang: str | None = None) -> dict:
    r = await client.post("/api/users/me/welcome", json={"lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


async def welcomed_user(client, db_session, current_user, lang: str | None = None):
    """A fresh account that has just been seeded, plus its group."""
    user = await make_user(db_session, "newbie@test.dev", "Newbie")
    current_user.id = user.id
    assert (await seed(client, lang))["created"] is True
    groups = (await client.get("/api/groups")).json()
    assert len(groups) == 1
    return user, groups[0]


async def test_seeding_creates_a_group_owing_ten_pln_to_splitdec(
    client, db_session, current_user
):
    user, group = await welcomed_user(client, db_session, current_user)
    assert group["name"] == WELCOME_TEXT["en"]["group"]

    detail = (await client.get(f"/api/groups/{group['id']}")).json()
    assert {m["id"] for m in detail["members"]} == {str(user.id), str(SYSTEM_USER_ID)}
    system = next(m for m in detail["members"] if m["id"] == str(SYSTEM_USER_ID))
    assert system["full_name"] == "SplitDec"

    expenses = (await client.get(f"/api/groups/{group['id']}/expenses")).json()
    assert len(expenses["items"]) == 1
    assert expenses["items"][0]["total_amount"] == "10.0000"
    assert expenses["items"][0]["paid_by_user_id"] == str(SYSTEM_USER_ID)

    # The whole point: a real, unsettled debt the balance engine can see.
    balances = (await client.get(f"/api/groups/{group['id']}/balances")).json()
    assert balances["PLN"] == [
        {
            "from_user_id": str(user.id),
            "to_user_id": str(SYSTEM_USER_ID),
            "amount": "10.0000",
        }
    ]


async def test_language_picks_the_stored_wording(client, db_session, current_user):
    _, group = await welcomed_user(client, db_session, current_user, lang="pl")
    assert group["name"] == WELCOME_TEXT["pl"]["group"]


async def test_unknown_language_falls_back_to_english(client, db_session, current_user):
    _, group = await welcomed_user(client, db_session, current_user, lang="de")
    assert group["name"] == WELCOME_TEXT["en"]["group"]


async def test_seeding_twice_creates_nothing(client, db_session, current_user):
    await welcomed_user(client, db_session, current_user)
    assert (await seed(client))["created"] is False
    assert len((await client.get("/api/groups")).json()) == 1


async def test_a_deleted_welcome_group_is_never_re_seeded(
    client, db_session, current_user
):
    """`welcomed_at` outlives the group, so settling and tidying up is final."""
    user, group = await welcomed_user(client, db_session, current_user)
    await client.post(
        f"/api/groups/{group['id']}/settlements",
        json={
            "paid_by_user_id": str(user.id),
            "paid_to_user_id": str(SYSTEM_USER_ID),
            "amount": "10.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    assert (await client.delete(f"/api/groups/{group['id']}")).status_code == 204

    assert (await seed(client))["created"] is False
    assert (await client.get("/api/groups")).json() == []


async def test_the_group_cannot_be_left_or_deleted_until_settled(
    client, db_session, current_user
):
    user, group = await welcomed_user(client, db_session, current_user)

    leaving = await client.delete(f"/api/groups/{group['id']}/members/{user.id}")
    assert leaving.status_code == 400
    assert "PLN" in leaving.json()["detail"]

    deleting = await client.delete(f"/api/groups/{group['id']}")
    assert deleting.status_code == 400
    assert "PLN" in deleting.json()["detail"]

    # Settling is the way out, and it is the ordinary settlement endpoint.
    r = await client.post(
        f"/api/groups/{group['id']}/settlements",
        json={
            "paid_by_user_id": str(user.id),
            "paid_to_user_id": str(SYSTEM_USER_ID),
            "amount": "10.00",
            "currency": "PLN",
        },
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    assert (await client.delete(f"/api/groups/{group['id']}")).status_code == 204


async def test_splitdec_cannot_be_removed_while_it_is_owed(
    client, db_session, current_user
):
    _, group = await welcomed_user(client, db_session, current_user)
    r = await client.delete(f"/api/groups/{group['id']}/members/{SYSTEM_USER_ID}")
    assert r.status_code == 400
    assert "PLN" in r.json()["detail"]


async def test_account_deletion_is_not_blocked_by_the_coffee(
    client, db_session, current_user
):
    """The debt is owed to us, so refusing erasure over it would be an
    obstacle we invented. The group goes with the account."""
    user, group = await welcomed_user(client, db_session, current_user)

    assert (await client.delete("/api/users/me")).status_code == 204

    async with db_session() as s:
        assert await s.get(Group, uuid.UUID(group["id"])) is None
        # Nothing of the group survives, SplitDec's own membership included.
        assert (
            await s.execute(
                select(func.count()).select_from(GroupMember).where(
                    GroupMember.group_id == uuid.UUID(group["id"])
                )
            )
        ).scalar_one() == 0
        assert (
            await s.execute(
                select(func.count()).select_from(Expense).where(
                    Expense.group_id == uuid.UUID(group["id"])
                )
            )
        ).scalar_one() == 0
        # SplitDec itself is untouched — it is shared by every welcome group.
        assert await s.get(User, SYSTEM_USER_ID) is not None


async def test_account_deletion_still_refuses_once_a_real_person_is_in_there(
    client, db_session, current_user
):
    """The exemption is narrow on purpose: invite somebody real into the
    welcome group and it holds debts between real people again."""
    user, group = await welcomed_user(client, db_session, current_user)
    friend = await make_user(db_session, "friend@test.dev", "Friend")
    async with db_session() as s:
        s.add(GroupMember(group_id=uuid.UUID(group["id"]), user_id=friend.id))
        await s.commit()

    r = await client.delete("/api/users/me")
    assert r.status_code == 400
    assert "PLN" in r.json()["detail"]


async def test_seeding_does_not_spend_the_group_quota(client, db_session, current_user):
    """The quotas brake what a caller creates; this is the deployment seeding
    itself, and it must not cost the user their first slot."""
    from _src.models import WriteEvent

    await welcomed_user(client, db_session, current_user)
    async with db_session() as s:
        assert (
            await s.execute(select(func.count()).select_from(WriteEvent))
        ).scalar_one() == 0
