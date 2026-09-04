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

**If that exits 1 with no output whatsoever**, the process aborted rather than
failed: on a Windows machine behind TLS-inspecting antivirus, the uv-managed
interpreter's statically linked OpenSSL kills the process on the first TLS
handshake ("OPENSSL_Uplink ... no OPENSSL_Applink"), before pytest writes a
byte. It is the same problem `api/_src/dev_loop.py` exists to solve for
`npm run api`, and the same workaround applies -- pop `SSLKEYLOGFILE` and
`truststore.inject_into_ssl()` before anything opens a socket. Nothing here can
do it for you: pytest imports this module long after the interpreter has
started. The Postgres tests keyed to TEST_DATABASE_URL hit it too.
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
    # Same connect_args dance as api/_src/db.py, and for the same reason: this
    # points at the transaction pooler (port 6543), where server-side prepared
    # statements do not survive between statements, so asyncpg has to be told
    # not to use them. Conditional rather than unconditional because psycopg —
    # the fallback driver on setups where asyncpg's TLS stack will not build —
    # takes neither argument.
    connect_args: dict[str, int] = {}
    if "+asyncpg" in AUDIT_DATABASE_URL:
        connect_args = {"statement_cache_size": 0, "prepared_statement_cache_size": 0}
    engine = create_async_engine(
        AUDIT_DATABASE_URL, poolclass=NullPool, connect_args=connect_args
    )
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


# The role the API connects as since 20260904100000. Everything below is the
# other half of that migration: the file says what was granted, these ask the
# database what the role can actually reach.
APP_ROLE = "splitdec_app"
APP_TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")


async def test_the_app_role_can_reach_every_table_in_public(catalog):
    """The outage-shaped failure, not the security-shaped one.

    20260904100000 grants on ALL TABLES *and* sets the schema's default
    privileges, so a table created later by postgres arrives reachable. A table
    created any other way does not, and the first sign of it would be
    `permission denied` from a production endpoint. Cheap to check here.
    """
    missing = (
        await catalog.execute(
            text(
                """
                SELECT c.relname, p.priv
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 CROSS JOIN unnest(:privs) AS p(priv)
                 WHERE n.nspname = 'public'
                   AND c.relkind IN ('r', 'p')
                   AND NOT has_table_privilege(:role, c.oid, p.priv)
                 ORDER BY c.relname, p.priv
                """
            ),
            {"role": APP_ROLE, "privs": list(APP_TABLE_PRIVILEGES)},
        )
    ).all()
    assert missing == [], (
        f"{APP_ROLE} cannot reach table(s) in schema public: "
        f"{[tuple(r) for r in missing]}. The app connects as this role -- these "
        "are 'permission denied' in production. Grant them, and find out why the "
        "default privileges in 20260904100000 did not cover it (most likely the "
        "table was created by a role other than postgres)."
    )


async def test_the_app_role_holds_nothing_outside_public(catalog):
    """The whole point of the exercise.

    `postgres` -- what the app used to connect as -- has USAGE on `auth` and
    SELECT/UPDATE/DELETE on `auth.users`, `auth.sessions` and
    `auth.refresh_tokens`, plus USAGE on storage, vault, graphql and realtime
    through its membership in anon/authenticated/service_role. A stolen
    DATABASE_URL was worth all of that. This asserts the replacement is worth
    exactly eight tables in one schema.

    Account deletion still removes an `auth.users` row; it does it through
    public.delete_auth_user, a SECURITY DEFINER wrapper that runs as postgres,
    which is why no privilege in `auth` is needed here.
    """
    schemas = (
        await catalog.execute(
            text(
                r"""
                SELECT n.nspname,
                       has_schema_privilege(:role, n.oid, 'USAGE')  AS usage,
                       has_schema_privilege(:role, n.oid, 'CREATE') AS create_
                  FROM pg_namespace n
                 WHERE n.nspname NOT IN ('public', 'information_schema')
                   AND n.nspname NOT LIKE 'pg\_%'
                   AND (has_schema_privilege(:role, n.oid, 'USAGE')
                        OR has_schema_privilege(:role, n.oid, 'CREATE'))
                 ORDER BY n.nspname
                """
            ),
            {"role": APP_ROLE},
        )
    ).all()
    assert schemas == [], (
        f"{APP_ROLE} holds schema privileges outside public: "
        f"{[tuple(r) for r in schemas]}. Either it was granted them or it was "
        "made a member of a role that has them -- see the memberships test below."
    )

    tables = (
        await catalog.execute(
            text(
                """
                SELECT table_schema, table_name, privilege_type
                  FROM information_schema.role_table_grants
                 WHERE grantee = :role AND table_schema <> 'public'
                 ORDER BY table_schema, table_name, privilege_type
                """
            ),
            {"role": APP_ROLE},
        )
    ).all()
    assert tables == [], (
        f"{APP_ROLE} holds table grants outside public: {[tuple(r) for r in tables]}"
    )


async def test_the_app_role_has_no_attributes_and_no_memberships(catalog):
    """`postgres` carries CREATEROLE, CREATEDB and BYPASSRLS and is a member of
    anon, authenticated, service_role, authenticator, pg_read_all_data and
    more. Every one of those is a way for the role above to quietly grow back
    what it was created without -- membership especially, since it is one GRANT
    away and leaves the grants tests above still passing on their own terms.

    NOINHERIT is asserted too: it is the second lock on the same door, so a
    membership added by accident still needs an explicit SET ROLE to be worth
    anything.
    """
    row = (
        await catalog.execute(
            text(
                """
                SELECT r.rolsuper, r.rolcreaterole, r.rolcreatedb,
                       r.rolbypassrls, r.rolinherit, r.rolreplication,
                       COALESCE((SELECT string_agg(g.rolname, ', ' ORDER BY g.rolname)
                                   FROM pg_auth_members m
                                   JOIN pg_roles g ON g.oid = m.roleid
                                  WHERE m.member = r.oid), '') AS memberships
                  FROM pg_roles r
                 WHERE r.rolname = :role
                """
            ),
            {"role": APP_ROLE},
        )
    ).first()
    assert row is not None, (
        f"role {APP_ROLE} does not exist. It is created out of band rather than "
        "by a migration, because the statement carries a password and this repo "
        "is public -- see 20260904100000."
    )
    super_, createrole, createdb, bypassrls, inherit, replication, memberships = row
    assert not super_, f"{APP_ROLE} is a superuser"
    assert not createrole, f"{APP_ROLE} has CREATEROLE"
    assert not createdb, f"{APP_ROLE} has CREATEDB"
    assert not bypassrls, f"{APP_ROLE} has BYPASSRLS"
    assert not replication, f"{APP_ROLE} has REPLICATION"
    assert not inherit, f"{APP_ROLE} is INHERIT -- it must be NOINHERIT"
    assert memberships == "", (
        f"{APP_ROLE} is a member of: {memberships}. It must be a member of "
        "nothing; membership is how it silently re-inherits what this role "
        "exists to do without."
    )


async def test_the_auth_user_wrapper_is_reachable_by_the_app_role_alone(catalog):
    """public.delete_auth_user is a privilege-escalation surface by
    construction: it runs as postgres and deletes any auth user by id. That is
    acceptable only while EXECUTE reaches exactly one role.

    The API-roles test above already forbids anon/authenticated/PUBLIC on every
    function here. This is the positive half -- the app role can call it (or
    account deletion 500s in production) and no other non-superuser can.
    """
    rows = (
        await catalog.execute(
            text(
                r"""
                SELECT r.rolname
                  FROM pg_proc p
                  JOIN pg_namespace n ON n.oid = p.pronamespace
                 CROSS JOIN pg_roles r
                 WHERE n.nspname = 'public'
                   AND p.proname = 'delete_auth_user'
                   AND NOT r.rolsuper
                   AND r.rolname NOT LIKE 'pg\_%'
                   AND has_function_privilege(r.rolname, p.oid, 'EXECUTE')
                 ORDER BY r.rolname
                """
            )
        )
    ).all()
    holders = {name for (name,) in rows}
    assert holders, (
        "public.delete_auth_user does not exist -- 20260904100000 was written "
        "but never applied."
    )
    assert APP_ROLE in holders, (
        f"{APP_ROLE} cannot execute public.delete_auth_user -- account deletion "
        "fails in production. The GRANT from 20260904100000 was never applied."
    )
    # postgres owns it, so it holds EXECUTE unconditionally; service_role is
    # Supabase's trusted server-side key and never reaches a browser.
    unexpected = holders - {APP_ROLE, "postgres", "service_role"}
    assert unexpected == set(), (
        f"public.delete_auth_user is executable by {sorted(unexpected)}. Whoever "
        "can call it can delete any auth user; EXECUTE must never be widened."
    )
