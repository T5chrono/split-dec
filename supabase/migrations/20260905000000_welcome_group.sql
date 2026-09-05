-- The welcome group: one seeded group per account, with SplitDec on the other
-- side of one unsettled 10 PLN coffee. See api/_src/welcome.py for why it is
-- shaped this way; this file only creates the two things the database has to
-- hold for it.

-- Which accounts have already been given one. Claimed by a conditional UPDATE
-- (`SET welcomed_at = now() WHERE id = ? AND welcomed_at IS NULL`), so the row
-- is its own lock and two parallel first requests cannot both win.
--
-- Nullable with no default and no backfill, which is a decision rather than an
-- omission: every account that exists today reads as un-welcomed and is seeded
-- on its next sign-in. On a just-launched app that is the intent -- the group
-- is meant to live with everybody, not only with people who arrive after this
-- deploy. Backfilling `now()` here is the one-line change that would limit it
-- to genuinely new signups.
--
-- No grant goes with this: `splitdec_app` holds table-level UPDATE on
-- public.users (20260904100000), which covers columns added later.
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS welcomed_at TIMESTAMPTZ;

-- The counterparty. An ordinary users row with no `auth.users` behind it --
-- there is no FK between the two tables (20260702000000), which is exactly
-- what lets this exist without an identity anybody could sign in as, reset a
-- password for, or steal a session from.
--
-- The address is RESERVED, not decorative. `handle_new_user` mirrors every
-- signup into public.users, where `email` is UNIQUE; a real account registered
-- at support@split-dec.app would therefore fail to be mirrored and land in the
-- app with no profile row. Do not sign up with it, and do not hand it out as a
-- contact address -- privacy@split-dec.app (src/lib/legal.ts) is the one for
-- that. It is visible: MembersTab renders each member's address under their
-- name, so every welcome group shows it.
--
-- welcomed_at is set on this row so it is never itself a seeding candidate.
--
-- Idempotent so a re-run, a branch or a restore is a no-op. The id is fixed in
-- api/_src/welcome.py (SYSTEM_USER_ID) and the two must never disagree.
INSERT INTO public.users (id, email, full_name, avatar_url, welcomed_at)
VALUES (
  '527bcd3f-9fb3-48f2-81dd-20023fa3dacc',
  'support@split-dec.app',
  'SplitDec',
  NULL,
  NOW()
)
ON CONFLICT (id) DO NOTHING;
