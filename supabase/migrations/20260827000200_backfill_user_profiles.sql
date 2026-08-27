-- Backfill what the UPDATE trigger could not have caught.
--
-- 20260827000100 added handle_user_updated, so public.users now follows
-- auth.users from that moment on. It cannot repair drift that accumulated
-- before it existed: every address change, name change and avatar refresh
-- since signup landed in auth.users alone, and everything downstream reads the
-- copy — invitation matching by lowercased email most of all.
--
-- Its own migration rather than an edit to 20260827000100, which is already
-- applied; and separate from the initial schema for the same reason.
--
-- Verified to affect zero rows on the production database at the time it was
-- written (all active accounts were already in step). It is here because the
-- trigger's guarantee should hold for any database this schema is applied to —
-- a restored dump, a branch, a fresh environment — and not only for the one it
-- happened to be written against.
--
-- Same three guards as the trigger, for the same reasons: never repopulate an
-- account anonymized by deletion, never overwrite a value with NULL, and never
-- touch created_at. The final predicate makes it a true no-op when nothing has
-- drifted, so re-running it rewrites no rows and bumps no autovacuum work.

UPDATE public.users u
SET
  email = COALESCE(a.email, u.email),
  full_name = COALESCE(
    a.raw_user_meta_data->>'full_name',
    a.raw_user_meta_data->>'name',
    u.full_name
  ),
  avatar_url = COALESCE(
    a.raw_user_meta_data->>'avatar_url',
    a.raw_user_meta_data->>'picture',
    u.avatar_url
  )
FROM auth.users a
WHERE a.id = u.id
  AND u.email NOT LIKE '%@users.splitdec.invalid'
  AND (
    u.email IS DISTINCT FROM COALESCE(a.email, u.email)
    OR u.full_name IS DISTINCT FROM COALESCE(
      a.raw_user_meta_data->>'full_name',
      a.raw_user_meta_data->>'name',
      u.full_name
    )
    OR u.avatar_url IS DISTINCT FROM COALESCE(
      a.raw_user_meta_data->>'avatar_url',
      a.raw_user_meta_data->>'picture',
      u.avatar_url
    )
  );
