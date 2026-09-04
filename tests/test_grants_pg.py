"""Optional integration test: the deployed database's grants and ACLs.

Every other check on the Data API lockdown is static -- test_migrations.py reads
the .sql files and asserts that the rules were *written*. Nothing asserted they
were *applied*, and the two came apart once already: 20260827000100 added a
SECURITY DEFINER function that carried `anon=X/postgres` in production for a
week, and it took a person reading pg_proc by hand to notice. A file in
supabase/migrations is a statement of intent; this file is the only thing in the
repo that looks at what the database actually says.

**AUDIT_DATABASE_URL, deliberately not TEST_DATABASE_URL.** The other Postgres
tests write rows and are documented as never being pointed at production. This
one is the opposite: it only reads catalogs, and it is *worthless* anywhere but
production, because the drift it looks for is created by things that happen to
the live project -- a table added through the dashboard, a Supabase feature
enabling itself. Two variables so neither habit can be applied to the wrong one.

Run it after adding a table, after turning on a Supabase feature, and before a
release:

    AUDIT_DATABASE_URL='postgresql+asyncpg://postgres.<ref>:<pw>@...:6543/postgres' \
      python -m pytest tests/test_grants_pg.py -v
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

AUDIT_DATABASE_URL = os.getenv("AUDIT_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not AUDIT_DATABASE_URL, reason="AUDIT_DATABASE_URL not set"
)

# The roles the Data API authenticates as. `anon` is what the publishable key in
# the frontend bundle maps to; `authenticated` is what any signed-in browser
# holds. Neither may reach anything in `public`: FastAPI is the sole
# authorization boundary in this deployment and RLS is off, so a grant to either
# of these is not "defence in depth missing", it is the boundary bypassed.
API_ROLES = ("anon", "authenticated")


@pytest.fixture
async def catalog():
    engine = create_async_engine(AUDIT_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()


async def test_the_api_roles_hold_no_table_grants(catalog):
    rows = (
        await catalog.execute(
            text(
                """
                SELECT table_name, grantee, privilege_type
                  FROM information_schema.role_table_grants
                 WHERE table_schema = 'public' AND grantee = ANY(:roles)
                 ORDER BY table_name, grantee, privilege_type
                """
            ),
            {"roles": list(API_ROLES)},
        )
    ).all()
    assert rows == [], (
        "anon/authenticated hold table grants in schema public: "
        f"{[tuple(r) for r in rows]}. The table was created by a role whose "
        "default privileges still grant to the API roles -- REVOKE ALL on it, "
        "then find out which role created it."
    )


async def test_the_api_roles_hold_no_sequence_grants(catalog):
    rows = (
        await catalog.execute(
            text(
                """
                SELECT object_name, grantee, privilege_type
                  FROM information_schema.role_usage_grants
                 WHERE object_schema = 'public' AND grantee = ANY(:roles)
                 ORDER BY object_name, grantee
                """
            ),
            {"roles": list(API_ROLES)},
        )
    ).all()
    assert rows == [], f"anon/authenticated hold sequence grants: {[tuple(r) for r in rows]}"


async def test_no_function_in_public_is_executable_by_the_api_roles(catalog):
    """The check test_migrations.py cannot make.

    That one asserts a REVOKE was written for every SECURITY DEFINER function it
    can parse. This one asks the database, so it also covers a function created
    outside the migrations directory entirely -- and it covers every function,
    not just the SECURITY DEFINER ones, because `public` is Data API territory
    and the FastAPI layer is meant to be the only way in.
    """
    rows = (
        await catalog.execute(
            text(
                """
                SELECT p.proname, r.rolname
                  FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                 CROSS JOIN unnest(ARRAY['anon', 'authenticated', 'public']) AS r(rolname)
                 WHERE n.nspname = 'public'
                   AND has_function_privilege(r.rolname, p.oid, 'EXECUTE')
                 ORDER BY p.proname, r.rolname
                """
            )
        )
    ).all()
    assert rows == [], (
        "function(s) in schema public are EXECUTE-able by an API role: "
        f"{[tuple(r) for r in rows]}. Add `REVOKE EXECUTE ON FUNCTION "
        "public.<name>(...) FROM PUBLIC, anon, authenticated;` to a migration "
        "and apply it."
    )


async def test_default_privileges_do_not_re_grant_to_the_api_roles(catalog):
    """The mechanism, not the symptom.

    Every finding above is downstream of a default ACL: an object inherits the
    grants of whichever role created it. 20260904000000 closed the last of the
    three for the postgres role (functions; tables and sequences went in
    20260702000001), so all three must now name postgres and service_role only.

    `supabase_admin`'s parallel entries are excluded because they cannot be
    changed -- the migration role is not a member of that role and is not a
    superuser, so no statement available to this project can alter them. They
    are inert while every object here is created as postgres, which is what the
    ownership test below is for.
    """
    rows = (
        await catalog.execute(
            text(
                """
                SELECT d.defaclobjtype, array_to_string(d.defaclacl, ' | ')
                  FROM pg_default_acl d
                  JOIN pg_namespace n ON n.oid = d.defaclnamespace
                 WHERE n.nspname = 'public'
                   AND pg_get_userbyid(d.defaclrole) = 'postgres'
                 ORDER BY d.defaclobjtype
                """
            )
        )
    ).all()
    assert rows, "no default privileges recorded for postgres in schema public"
    for objtype, acl in rows:
        for role in API_ROLES:
            assert f"{role}=" not in acl, (
                f"postgres' default privileges for object type '{objtype}' still "
                f"grant to {role} ({acl}) -- the next object created here arrives "
                "reachable through the Data API."
            )


async def test_every_object_in_public_is_owned_by_postgres(catalog):
    """Why supabase_admin's untouchable default ACL stays harmless.

    A default ACL only applies to objects created by the role it names. All of
    ours are created by postgres, whose defaults are locked down above. The day
    something in `public` is owned by supabase_admin instead, that object was
    created by a path the migrations do not control and it inherited grants to
    anon and authenticated on the way in.
    """
    rows = (
        await catalog.execute(
            text(
                """
                SELECT c.relname, pg_get_userbyid(c.relowner)
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                   AND c.relkind IN ('r', 'S', 'v', 'm', 'p')
                   AND pg_get_userbyid(c.relowner) <> 'postgres'
                 ORDER BY c.relname
                """
            )
        )
    ).all()
    assert rows == [], (
        f"object(s) in schema public are not owned by postgres: {[tuple(r) for r in rows]}. "
        "Check their grants: they inherited whatever their creator's default "
        "privileges say, which for supabase_admin means anon and authenticated."
    )


async def test_rls_is_off_on_purpose_and_stays_measured(catalog):
    """Not a security assertion -- a documentation one.

    RLS is intentionally disabled (CLAUDE.md; the Data API grants were revoked
    instead). This pins the fact so that "RLS is off" stays a decision someone
    made rather than something nobody has looked at since, and so a table that
    silently *gains* RLS -- which would change how the FastAPI layer's queries
    behave, since they connect as a role RLS applies to -- shows up here.
    """
    rows = (
        await catalog.execute(
            text(
                """
                SELECT c.relname, c.relrowsecurity
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public' AND c.relkind = 'r'
                 ORDER BY c.relname
                """
            )
        )
    ).all()
    assert rows, "no tables found in schema public"
    enabled = [name for name, rls in rows if rls]
    assert enabled == [], (
        f"RLS was enabled on {enabled}. That is a deliberate deviation in this "
        "codebase (FastAPI is the sole authorization boundary) -- if this is "
        "intended, CLAUDE.md and this test both need to change together."
    )
