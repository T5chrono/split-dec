-- RLS stays disabled per spec; the FastAPI backend (trusted role) is the sole
-- authorization boundary. To make that actually true, revoke all access that
-- Supabase's auto-generated Data API (PostgREST) roles would otherwise have,
-- so the anon/publishable key cannot read or write these tables directly.

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;

-- The auth-sync trigger function must not be callable via /rest/v1/rpc.
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM PUBLIC, anon, authenticated;
