-- The API stops connecting as the database owner.
--
-- Until now `DATABASE_URL` names `postgres`, which owns all eight tables and,
-- measured on production while writing this, also carries CREATEROLE, CREATEDB,
-- BYPASSRLS, membership in anon/authenticated/service_role/authenticator, and
-- SELECT/UPDATE/DELETE on `auth.users`, `auth.sessions` and
-- `auth.refresh_tokens`. The app needs none of that. It reads and writes eight
-- tables in `public`, takes row and advisory locks, and deletes exactly one row
-- from `auth.users` when an account is deleted.
--
-- This changes nothing about authorization -- FastAPI remains the sole
-- boundary and RLS stays off (see CLAUDE.md). It only shrinks what a leaked
-- connection string is worth.
--
-- The role's password is NOT here, and must never be: this directory is
-- committed to a public repository. The real, LOGIN-capable `splitdec_app` was
-- created out of band (Supabase SQL editor / MCP) with the password going
-- straight into Vercel and the local `.env`:
--
--   CREATE ROLE splitdec_app WITH LOGIN PASSWORD '<generated>'
--     NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
--
-- NOINHERIT and the empty membership list are the point: `postgres` is a member
-- of anon, authenticated and service_role, and this role must not pick up
-- anything similar by accident. Grant it no memberships, ever.

-- A database that has never seen that out-of-band statement -- a preview
-- branch, a restore, a fresh project -- would otherwise fail on the first GRANT
-- below. So create the role there, deliberately **NOLOGIN**: it is a grantee,
-- not a credential, and nothing can connect as it. On production this block is
-- a no-op and leaves the real role's LOGIN and password alone.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'splitdec_app') THEN
    CREATE ROLE splitdec_app
      NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
  END IF;
END
$$;

GRANT USAGE ON SCHEMA public TO splitdec_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO splitdec_app;

-- So a table added later is not silently unreachable by the app. Note the
-- asymmetry with 20260904000000, which *revoked* the function defaults for
-- anon/authenticated: that entry governs roles a browser reaches with the
-- publishable key, this one governs an internal role that never leaves the
-- serverless function. Opposite intent, same mechanism -- do not "tidy" them
-- into looking alike.
--
-- Like every ALTER DEFAULT PRIVILEGES here it applies to objects created by the
-- current role, postgres. That is the same condition
-- tests/test_grants_pg.py::test_every_object_in_public_is_owned_by_postgres
-- already pins.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO splitdec_app;

-- Nothing is granted for sequences because there are none: every id is a UUID
-- generated in Python. A sequence added later needs USAGE added here too.

-- Account deletion removes the caller's `auth.users` row, which is what
-- actually revokes sign-in. `splitdec_app` cannot be given that privilege
-- directly: `postgres` holds DELETE on `auth.users` *without* grant option
-- (verified -- `has_table_privilege('postgres','auth.users','DELETE WITH GRANT
-- OPTION')` is false), so it cannot pass it on. A SECURITY DEFINER wrapper is
-- therefore mandatory rather than stylistic.
--
-- Created as postgres, so it runs with the privilege that can do the delete.
-- `SET search_path = ''` plus the schema-qualified table is what stops it being
-- a search-path hijack target (Supabase's own linter flags the omission).
CREATE OR REPLACE FUNCTION public.delete_auth_user(target uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$ DELETE FROM auth.users WHERE id = target $$;

-- Mandatory, and not only as hygiene: `public` is Data API territory, a
-- function there is reachable at /rest/v1/rpc/<name>, and
-- tests/test_migrations.py fails CI for any SECURITY DEFINER function in this
-- schema without a REVOKE shaped exactly like this.
--
-- This function is a privilege-escalation surface by construction: whoever can
-- call it can delete any auth user. That is acceptable only because EXECUTE
-- reaches exactly one role. Never widen it.
REVOKE EXECUTE ON FUNCTION public.delete_auth_user(uuid) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.delete_auth_user(uuid) TO splitdec_app;
