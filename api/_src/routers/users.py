import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import verify_jwt
from ..balances import net_balances
from ..db import get_db
from ..deps import DELETED_EMAIL_SUFFIX, get_active_user, lock_groups_exclusive
from ..models import Group, GroupInvitation, GroupMember, WriteEvent
from ..ratelimit import INVITE, recipient_key
from ..schemas import WelcomeIn, WelcomeOut
from ..welcome import SYSTEM_USER_ID, seed_welcome_group, solo_welcome_groups
from .groups import purge_group

router = APIRouter(prefix="/users", tags=["users"])

# NOTE: GET /users/search was removed on security review — it let any
# authenticated caller probe whether an email is registered and fetch the
# name/avatar. The invitation flow covers the lookup use case with a smaller
# surface (membership required, an invitation record is created).


@router.post("/me/welcome", response_model=WelcomeOut)
async def ensure_welcome_group(
    body: WelcomeIn,
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Seed the caller's welcome group if they have never had one (welcome.py).

    Called by the client once per signed-in session and idempotent by
    construction, so a replay, a StrictMode double-effect or two tabs opening
    at once all resolve to `created: false` rather than a second group.

    Deliberately a POST the client makes, not something folded into
    `GET /groups`: the groups list is on the hot path of every navigation, and
    a read endpoint that writes would have to carry this whole protocol.

    The lock is `"exclusive"`, not the `"shared"` that the other
    membership-creating endpoints take. Two reasons, and they point the same
    way: this also UPDATEs the caller's own `users` row, and two concurrent
    requests that each took the shared lock first would deadlock on upgrading
    it. `FOR NO KEY UPDATE` serializes them cleanly and still leaves the FK
    inserts below (which take `FOR KEY SHARE` on `users`) unblocked.
    """
    user = await get_active_user(db, caller, lock="exclusive")
    group = await seed_welcome_group(db, user, body.lang)
    await db.commit()
    return WelcomeOut(created=group is not None)


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    caller: uuid.UUID = Depends(verify_jwt),
):
    """Delete the caller's account.

    Refuses while the caller has a non-zero balance in any currency of any
    group. Ledger history (expenses/settlements they took part in) is kept
    for the other members, so the public.users row is anonymized rather than
    deleted; the auth.users row is removed, which revokes all sign-in.
    """
    # Taken before the membership snapshot below and held to commit: group
    # creation and invitation acceptance take the matching shared lock, so a
    # membership created concurrently cannot slip past the balance checks or
    # outlive the unscoped delete. See deps.get_active_user.
    user = await get_active_user(db, caller, lock="exclusive")
    old_email = user.email.lower()

    group_ids = sorted(
        (
            await db.execute(
                select(GroupMember.group_id).where(GroupMember.user_id == caller)
            )
        ).scalars().all()
    )
    # Exclusive locks on every group: no expense/settlement write (shared
    # lock) can slip in between the zero-balance checks below and the
    # membership removal.
    await lock_groups_exclusive(db, group_ids)
    # The welcome group's 10 PLN is owed to SplitDec itself (welcome.py), and
    # refusing an account deletion over it would put an obstacle we invented in
    # front of the one request a person is always entitled to make. Skipped
    # here, and purged below.
    #
    # Only while the group is still just them and SplitDec. Invite somebody
    # real in and it holds debts between real people, so the ordinary rule
    # comes back — and clearing it is the same two clicks as any other group,
    # so nobody is stuck either way.
    exempt = await solo_welcome_groups(db, group_ids)
    unsettled: set[str] = set()
    for group_id in group_ids:
        if group_id in exempt:
            continue
        buckets = await net_balances(db, group_id)
        unsettled.update(
            c for c, users in buckets.items() if users.get(caller, 0) != 0
        )
    if unsettled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete account with outstanding balances in: "
                + ", ".join(sorted(unsettled))
            ),
        )

    # Single transaction: leave groups, drop invitations, anonymize PII,
    # revoke sign-in.
    await db.execute(delete(GroupMember).where(GroupMember.user_id == caller))
    # A group this empties goes with the account. Every route into a group is
    # membership-gated, so one with no members can never again be read, settled
    # or deleted by anybody — it would just outlive everyone who could account
    # for it. remove_member refuses the same situation instead of deciding it
    # (routers/groups.py); here there is nobody left to ask. The exclusive
    # locks taken above already cover each of these groups.
    #
    # SplitDec does not count as somebody left to account for the group: it
    # never signs in, so a welcome group whose only human has just left is as
    # unreachable as an empty one, and would otherwise accumulate one row per
    # deleted account forever.
    for group_id in group_ids:
        remaining = (
            await db.execute(
                select(func.count())
                .select_from(GroupMember)
                .where(
                    GroupMember.group_id == group_id,
                    GroupMember.user_id != SYSTEM_USER_ID,
                )
            )
        ).scalar_one()
        if remaining == 0:
            await purge_group(db, await db.get(Group, group_id))
    # Pending invitations are capabilities that never expire and are matched
    # by email (invitations.my_invitations), so leaving them behind would
    # hand group access to whoever registers this address next.
    await db.execute(
        delete(GroupInvitation).where(
            GroupInvitation.status == "PENDING",
            (GroupInvitation.invited_user_id == caller)
            | (func.lower(GroupInvitation.email) == old_email),
        )
    )
    # Answered invitations stay as group history, but must not keep the
    # address on file — the users row is being anonymized for the same reason.
    await db.execute(
        update(GroupInvitation)
        .where(func.lower(GroupInvitation.email) == old_email)
        .values(email=f"deleted-{caller}{DELETED_EMAIL_SUFFIX}")
    )
    # Rate-limit tombstones (ratelimit.py). The LEDGER and GROUP ones are a
    # purely personal trace: they feed per-caller windows, and this caller will
    # never write again — sign-in is revoked below, and a replacement account
    # is a different user id with a fresh window regardless. They go.
    await db.execute(
        delete(WriteEvent).where(
            WriteEvent.user_id == caller, WriteEvent.kind != INVITE
        )
    )
    # The INVITE ones stay. Two of the three windows they feed count *shared*
    # resources — the sending domain's reputation (global) and one address's
    # share of it (per recipient) — so clearing them hands back allowance that
    # was spent, and account deletion becomes the reset button: invite an
    # address its three times, delete the account, sign up again, repeat. What
    # cannot stay is the digest of *this* account's own address, which after
    # the anonymization below would be the last thing on file derived from it.
    # Nulling the column keeps the row counting toward the global window while
    # erasing the address it was about — the per-recipient window it also fed
    # belongs to an address nobody can reach any more.
    await db.execute(
        update(WriteEvent)
        .where(WriteEvent.recipient_hash == recipient_key(old_email))
        .values(recipient_hash=None)
    )
    user.email = f"deleted-{caller}{DELETED_EMAIL_SUFFIX}"
    user.full_name = "Deleted user"
    user.avatar_url = None
    # Revoking sign-in is the one thing this endpoint cannot do from `public`.
    # On Postgres it goes through public.delete_auth_user (20260904100000), a
    # SECURITY DEFINER wrapper, because the app's own role -- `splitdec_app`
    # since that migration -- has no privileges in the `auth` schema at all,
    # and could not be given the DELETE directly even by hand: `postgres` holds
    # it without grant option, so it cannot pass it on.
    #
    # The SQLite branch is the test suite's, where conftest.py fakes the schema
    # with `ATTACH ':memory:' AS auth` and no function exists. Dialect-aware SQL
    # has a precedent here (ratelimit.window_cutoff), but the cost is specific
    # and worth stating: **the production statement is not exercised by the
    # default suite.** Only a real Postgres run covers it --
    # tests/test_locks_pg.py calls the wrapper as the app role, which needs
    # TEST_DATABASE_URL, and tests/test_grants_pg.py checks the EXECUTE grant
    # behind it against the live catalogs.
    if db.get_bind().dialect.name == "sqlite":
        await db.execute(
            text("DELETE FROM auth.users WHERE id = :uid"), {"uid": str(caller)}
        )
    else:
        await db.execute(
            text("SELECT public.delete_auth_user(:uid)"), {"uid": str(caller)}
        )
    await db.commit()
