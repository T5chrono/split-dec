-- Carry the Data API lockdown forward to the second trigger function.
--
-- 20260702000001_lock_down_data_api.sql revoked EXECUTE on handle_new_user()
-- from PUBLIC/anon/authenticated, because a SECURITY DEFINER function in an
-- API-exposed schema is reachable at /rest/v1/rpc/<name> and the FastAPI layer
-- is meant to be the only authorization boundary. 20260827000100 then added
-- public.handle_user_updated() -- also SECURITY DEFINER, also owned by
-- postgres -- without carrying that rule forward, so it kept the Postgres
-- default of EXECUTE TO PUBLIC. Verified on production before this migration:
-- its ACL read `=X/postgres | ... | anon=X/postgres | authenticated=X/postgres`
-- while handle_new_user's read `postgres=X/postgres | service_role=X/postgres`.
--
-- Not known to be exploitable: it RETURNS trigger, PostgREST keeps
-- trigger-returning functions out of its schema cache, and Postgres refuses to
-- invoke one outside a trigger context. This closes the drift rather than a
-- hole -- but the rule is the repo's own, and nothing in CI was checking it.
-- tests/test_migrations.py now does.

REVOKE EXECUTE ON FUNCTION public.handle_user_updated() FROM PUBLIC, anon, authenticated;

-- Belt and braces on the table grants. Re-running the lockdown's REVOKE is a
-- no-op today (role_table_grants returns no rows for anon/authenticated on any
-- of the eight public tables, write_events included -- it was created after the
-- lockdown and inherited the revoked default), and it stays cheap insurance
-- against a table created out-of-band between then and now.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;

-- What this migration deliberately does NOT do, so the next reader stops
-- looking for it:
--
-- Supabase ships a second default-ACL entry, FOR ROLE supabase_admin, which
-- still grants anon/authenticated ALL on tables created in this schema:
--
--   supabase_admin -> postgres=arwdDxtm | anon=arwdDxtm
--                   | authenticated=arwdDxtm | service_role=arwdDxtm
--
-- Harmless while every table is created as postgres (all eight are, and the
-- lockdown already revoked the postgres-role default), but it is the one way a
-- future table could arrive world-readable through the Data API. It cannot be
-- fixed from here: ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin requires
-- membership in that role, and the migration role (postgres) is neither a
-- member nor a superuser. Revoking USAGE on the schema instead would work but
-- is not worth it -- PUBLIC holds USAGE as well, so it would have to come off
-- PUBLIC too, and the auth-trigger path runs through this schema.
--
-- So this is a thing to check rather than enforce. After adding a table:
--
--   SELECT table_name, grantee FROM information_schema.role_table_grants
--    WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated');
--
-- Anything but an empty result means the new table was created by a role whose
-- default privileges still grant to the API roles; REVOKE ALL on it and find
-- out which role created it.
