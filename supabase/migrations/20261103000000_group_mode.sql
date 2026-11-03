-- How a group treats money. 'SPLIT' is everything the app did before this
-- column existed: expenses are divided between members and leave balances to
-- settle. 'SHARED' is a common purse -- a couple with joint finances -- where
-- every expense is recorded against the person who paid it alone, so nobody
-- ever owes anybody and there is nothing to settle.
--
-- The SHARED behaviour lives entirely in the API (routers/expenses.py forces a
-- payer-only split, routers/settlements.py refuses settlements); nothing in
-- the balance computation knows about it, and its balances are zero because
-- of what is written, not because anything skips them.
--
-- The default backfills every existing group as 'SPLIT', which is what they
-- all are. No grant goes with this: `splitdec_app` holds table-level
-- SELECT/INSERT/UPDATE on public.groups (20260904100000), which covers
-- columns added later.
ALTER TABLE public.groups
  ADD COLUMN IF NOT EXISTS mode TEXT NOT NULL DEFAULT 'SPLIT'
  CONSTRAINT groups_mode_check CHECK (mode IN ('SPLIT', 'SHARED'));
