-- Keep public.users in step with auth.users after signup, not only at it.
--
-- handle_new_user (initial schema) copies a new auth.users row into
-- public.users and nothing has watched that row since. Everything downstream
-- reads the copy: invitations are matched by lowercased email
-- (api/_src/routers/invitations.py), and the members list, avatars and the
-- "who invited you" line all come from public.users. So a user who changes
-- their address in Supabase Auth -- or has their name or picture refreshed by
-- the identity provider -- keeps the old one here indefinitely: invitations
-- sent to their real address never appear, invitations sent to the address
-- they no longer own still do, and the group sees a name they have changed.
--
-- Guarded three ways, because this trigger runs inside somebody else's auth
-- transaction:
--
--  * An anonymized row is never repopulated. Account deletion
--    (api/_src/routers/users.py) rewrites public.users.email to
--    deleted-<id>@users.splitdec.invalid -- deps.DELETED_EMAIL_SUFFIX -- and
--    deletes the auth.users row in the same transaction. A DELETE does not
--    fire this trigger, but a soft-delete or any late UPDATE would, and
--    restoring the address is precisely what deletion promised not to do.
--  * NULL never overwrites a value. auth.users.email is nullable, and a
--    provider that stops returning a name or picture must not blank the one
--    already on file; public.users.email is NOT NULL besides.
--  * The WHEN clause keeps it off the hot path. auth.users is updated on every
--    sign-in and token refresh, and none of those touch these columns.

CREATE OR REPLACE FUNCTION public.handle_user_updated()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  UPDATE public.users u
  SET
    email = COALESCE(NEW.email, u.email),
    full_name = COALESCE(
      NEW.raw_user_meta_data->>'full_name',
      NEW.raw_user_meta_data->>'name',
      u.full_name
    ),
    avatar_url = COALESCE(
      NEW.raw_user_meta_data->>'avatar_url',
      NEW.raw_user_meta_data->>'picture',
      u.avatar_url
    )
  WHERE u.id = NEW.id
    AND u.email NOT LIKE '%@users.splitdec.invalid';
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_updated
  AFTER UPDATE ON auth.users
  FOR EACH ROW
  WHEN (
    OLD.email IS DISTINCT FROM NEW.email
    OR OLD.raw_user_meta_data IS DISTINCT FROM NEW.raw_user_meta_data
  )
  EXECUTE FUNCTION public.handle_user_updated();
