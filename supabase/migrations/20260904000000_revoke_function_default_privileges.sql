-- Close the hole that let handle_user_updated() ship world-executable.
--
-- 20260901000000 fixed that function's ACL but not the reason it had the wrong
-- one. Checked against production while writing this migration, the postgres
-- role's default privileges for FUNCTIONS in schema public still read:
--
--   postgres=X/postgres | anon=X/postgres
--                       | authenticated=X/postgres | service_role=X/postgres
--
-- So every function created as postgres in this schema arrives EXECUTE-able by
-- anon and authenticated -- the two roles the publishable key in the frontend
-- bundle maps to. That is not a property of handle_user_updated; it is the
-- default, and the next SECURITY DEFINER function anyone adds inherits it. The
-- previous migration's REVOKE was a fix for one object where the class of
-- object was the problem.
--
-- 20260702000001's lockdown did the equivalent for TABLES and SEQUENCES (both
-- of those default ACLs already read postgres + service_role only) and simply
-- did not carry the same rule to functions. This is that rule.
--
-- Applies to the current role, postgres, which owns all eight tables and both
-- functions -- so it governs everything a migration creates. service_role
-- keeps EXECUTE, exactly as it kept its table grants: it is the trusted
-- server-side key, not one that reaches a browser.

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated;

-- Belt and braces on the functions that already exist. A no-op today (both
-- trigger functions read `postgres=X/postgres | service_role=X/postgres` after
-- 20260901000000), and cheap insurance against one created out-of-band.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon, authenticated;

-- What this migration still deliberately does NOT do -- carried forward from
-- 20260901000000, now with the reason measured rather than assumed:
--
-- Supabase ships a second default-ACL entry FOR ROLE supabase_admin, which
-- grants anon/authenticated ALL on tables, EXECUTE on functions and rwU on
-- sequences created in this schema *by that role*. It cannot be changed from
-- here, and that is not a guess: on production,
--
--   SELECT pg_has_role(current_user, 'supabase_admin', 'MEMBER'),
--          (SELECT rolsuper FROM pg_roles WHERE rolname = current_user);
--
-- returns false, false. ALTER DEFAULT PRIVILEGES FOR ROLE requires membership
-- in the role whose defaults are being changed, so the migration role cannot
-- issue it and neither can the dashboard's SQL editor, which connects as the
-- same role. It is reachable only by Supabase themselves.
--
-- It stays harmless as long as every object in this schema is created as
-- postgres -- all eight tables and both functions are -- because a default ACL
-- only applies to objects created by the role it names. The exposure would be
-- an object created *as supabase_admin*, which is something only a dashboard
-- feature or a Supabase-side migration could do.
--
-- So it remains a thing to check rather than enforce, and the check is now
-- automated: tests/test_grants_pg.py asserts the whole catalog picture against
-- a live database (skipped unless AUDIT_DATABASE_URL is set). Run it after
-- adding a table, after enabling a Supabase feature that creates one, and
-- before a release. It fails loudly on exactly the drift described above.
