"""The revised category list, and the retired values it replaced."""

import re
from pathlib import Path

from conftest import expense_payload, idem

from _src.categories import LEGACY_CATEGORIES, Category

MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "20261105000000_categories_v2.sql"
)


def test_legacy_values_are_retired_not_current():
    # A retired value that is also a current one would be silently rewritten
    # on every save, and the migration would move rows that never needed it.
    current = {c.value for c in Category}
    assert not current & LEGACY_CATEGORIES.keys()


def test_migration_moves_rows_exactly_as_the_api_translates_them():
    sql = MIGRATION.read_text(encoding="utf-8")
    pairs = dict(re.findall(r"WHEN '([^']+)' THEN '([^']+)'", sql))
    assert pairs == {old: new.value for old, new in LEGACY_CATEGORIES.items()}
    in_list = re.search(r"WHERE category IN \((.*?)\);", sql, re.S)
    assert in_list is not None
    assert set(re.findall(r"'([^']+)'", in_list.group(1))) == LEGACY_CATEGORIES.keys()


async def test_new_category_accepted(client, two_user_group):
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]], category="AI subscriptions"),
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "AI subscriptions"


async def test_stale_client_category_is_translated_on_create(client, two_user_group):
    # An installed PWA still on the old bundle offers "Liquor"; refusing it
    # would make that client unable to record the expense at all.
    g = two_user_group
    r = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]], category="Liquor"),
        headers=idem(),
    )
    assert r.status_code == 201, r.text
    assert r.json()["category"] == "Alcohol"


async def test_stale_client_category_is_translated_on_patch(client, two_user_group):
    g = two_user_group
    created = await client.post(
        f"/api/groups/{g['group'].id}/expenses",
        json=expense_payload(g["alice"], [g["alice"]]),
        headers=idem(),
    )
    r = await client.patch(
        f"/api/expenses/{created.json()['id']}", json={"category": "TV/Phone/Internet"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "Internet"


def test_frontend_lists_the_same_categories_in_the_same_order():
    # The picker renders src/lib/categories.tsx; the API validates against the
    # enum. A value only one side knows is either unpickable or a 422.
    tsx = (
        Path(__file__).resolve().parent.parent / "src" / "lib" / "categories.tsx"
    ).read_text(encoding="utf-8")
    assert re.findall(r'\{ value: "([^"]+)"', tsx) == [c.value for c in Category]
