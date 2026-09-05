"""The welcome group every new account is seeded with.

One group, two members and one unsettled expense: SplitDec paid 10 PLN for a
coffee and the new account owes it. It is a working example of the app --
somewhere to open, poke at and settle without inventing a trip first -- and a
standing reminder that nothing here is paid for (src/lib/support.ts).

Three things about it are deliberate and load-bearing.

**The counterparty is a real `public.users` row, not a special case.** A group
with one member cannot hold a debt: net balance is `paid - owed`
(balances.py), so a lone member pays themselves and nets to zero, which would
leave nothing for `remove_member` and `delete_group` to refuse. Somebody has to
be on the other side of the expense. Making that somebody an ordinary row means
the balance engine, the members list, the settle form and the greedy
simplification all work on it unchanged, with no `if is_welcome` anywhere near
the money.

**Nobody can sign in as it.** `public.users.id` carries no foreign key to
`auth.users` (20260702000000), so the row exists without an auth identity and
there is no credential to steal or reset. `SYSTEM_USER_EMAIL` is on a domain
this project owns and is *reserved*: `handle_new_user` copies a new signup into
`public.users` and would hit the UNIQUE on `email`, so a real account
registered at that address would fail to be mirrored. Never hand it out.

**Seeding is claimed, not checked.** `users.welcomed_at` is set by a
conditional UPDATE whose WHERE includes `welcomed_at IS NULL`, so the row
itself is the lock and `rowcount` decides -- two parallel first requests cannot
both create a group, and neither can a client that retries. It is also why a
user who settles the expense and deletes the group never gets another: the
column outlives the group, exactly like the `write_events` tombstones outlive
the rows they authorized (ratelimit.py).

Neither the group nor the expense is charged to a quota. The quotas brake what
a *caller* creates (ratelimit.py); this is the deployment seeding itself, it
happens exactly once per account by construction, and spending the user's first
group slot on it would be charging them for a gift.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .categories import Category
from .models import Expense, ExpenseSplit, Group, GroupMember, User

# Fixed, because it is referenced from a migration, from here, and from every
# welcome group's rows. Generated once and never regenerated.
SYSTEM_USER_ID = uuid.UUID("527bcd3f-9fb3-48f2-81dd-20023fa3dacc")
SYSTEM_USER_NAME = "SplitDec"
# Shown to every member of a welcome group (MembersTab renders the address
# under the name), so it has to be presentable as well as reserved.
SYSTEM_USER_EMAIL = "support@split-dec.app"

# What the new account owes. A token amount in the currency of the app's home
# audience: the backend has no idea where the caller is at signup, and guessing
# from a header would make the seeded ledger differ between two people who
# signed up from the same kitchen.
WELCOME_AMOUNT = Decimal("10.0000")
WELCOME_CURRENCY = "PLN"

# The group name and the expense description are stored text, fixed at
# creation, so the caller's current language is the only chance to get them
# right. `lang` comes from the client's own i18n state (src/lib/i18n.tsx);
# anything unrecognised falls back to English rather than failing a request
# whose whole job is to be invisible.
WELCOME_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "group": "Welcome to SplitDec",
        "expense": "Buy me a coffee — support SplitDec",
    },
    "pl": {
        "group": "Witaj w SplitDec",
        "expense": "Postaw mi kawę — wesprzyj SplitDec",
    },
}


def welcome_text(lang: str | None) -> dict[str, str]:
    return WELCOME_TEXT.get((lang or "en").lower(), WELCOME_TEXT["en"])


async def ensure_system_user(db: AsyncSession) -> None:
    """Create the counterparty row if this database has never seen it.

    Production gets it from migration 20260905000000; a preview branch, a
    restore or the SQLite test suite (which builds its schema from the models)
    does not, and the first seeded account would otherwise fail a foreign key.
    Written through a SAVEPOINT so the loser of a race between two first-ever
    signups rolls back its own INSERT instead of poisoning the transaction the
    caller still needs -- and so this stays one statement on both dialects,
    rather than a Postgres ON CONFLICT and a SQLite OR IGNORE.
    """
    if await db.get(User, SYSTEM_USER_ID) is not None:
        return
    try:
        async with db.begin_nested():
            db.add(
                User(
                    id=SYSTEM_USER_ID,
                    email=SYSTEM_USER_EMAIL,
                    full_name=SYSTEM_USER_NAME,
                    # Never a seeding candidate itself: it has no auth identity
                    # and so can never call the endpoint, but the claim below is
                    # cheaper to reason about when no row is eligible twice.
                    welcomed_at=datetime.now(timezone.utc),
                )
            )
    except IntegrityError:
        pass


async def seed_welcome_group(
    db: AsyncSession, user: User, lang: str | None = None
) -> Group | None:
    """Give `user` their welcome group, once. Returns None if they already had it.

    Adds to the session without committing: the caller owns the transaction,
    which is what makes the claim below and the rows it authorizes atomic.
    Caller must already hold the user's exclusive lock (deps.get_active_user) --
    it creates a membership, so account deletion must not be able to snapshot
    this user's groups halfway through.
    """
    # The claim. `welcomed_at IS NULL` in the WHERE is the whole concurrency
    # story: whoever's UPDATE matches the row gets to build the group, and a
    # second request in flight matches nothing and is told it already exists.
    claimed = await db.execute(
        update(User)
        .where(User.id == user.id, User.welcomed_at.is_(None))
        .values(welcomed_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        return None

    await ensure_system_user(db)
    text = welcome_text(lang)

    group = Group(name=text["group"], created_by=SYSTEM_USER_ID)
    db.add(group)
    await db.flush()
    db.add(GroupMember(group_id=group.id, user_id=SYSTEM_USER_ID))
    db.add(GroupMember(group_id=group.id, user_id=user.id))

    expense = Expense(
        group_id=group.id,
        description=text["expense"],
        category=Category.DINING_OUT,
        # EXACT, with the single split below carrying the whole amount: the
        # payer owes none of it, which is what puts the new account 10 PLN
        # down and SplitDec 10 PLN up.
        split_type="EXACT",
        total_amount=WELCOME_AMOUNT,
        currency=WELCOME_CURRENCY,
        paid_by_user_id=SYSTEM_USER_ID,
        expense_date=date.today(),
        idempotency_key=uuid.uuid4(),
    )
    db.add(expense)
    await db.flush()
    db.add(
        ExpenseSplit(expense_id=expense.id, user_id=user.id, owed_amount=WELCOME_AMOUNT)
    )
    return group


async def solo_welcome_groups(
    db: AsyncSession, group_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Which of `group_ids` hold exactly one real member and SplitDec.

    Account deletion uses this to skip its zero-balance refusal
    (routers/users.py). The predicate is deliberately narrow: once somebody else
    has been invited in, the group holds debts between real people and the
    ordinary rule applies again.
    """
    if not group_ids:
        return set()
    rows = (
        await db.execute(
            select(GroupMember.group_id)
            .where(GroupMember.group_id.in_(group_ids))
            .group_by(GroupMember.group_id)
            .having(func.count() == 2)
            .having(
                func.sum(case((GroupMember.user_id == SYSTEM_USER_ID, 1), else_=0)) == 1
            )
        )
    ).scalars().all()
    return set(rows)
