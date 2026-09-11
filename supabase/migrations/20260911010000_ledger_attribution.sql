-- Who created and who last changed a ledger row.
--
-- Any member can create, edit and withdraw any expense or settlement in a group
-- they belong to -- that is the shared-ledger model and it is intentional. What
-- was missing is the record of who did it. The only person on the row was the
-- *payer*, which is a claim about money, not a statement about who typed it, so
-- "Bob changed my expense from 100 to 300" had no answer in the data and no
-- `updated_at` to even show that it had changed.
--
-- All three columns are nullable and there is deliberately no backfill. The rows
-- that predate this migration have no author on record, and inferring one from
-- `paid_by_user_id` would invent a fact -- the payer is often not who entered it.
-- A visible blank beats a plausible fiction in a ledger.
--
-- No grants here: splitdec_app already holds table-level DML on both tables
-- (20260904100000), which covers columns added later.

alter table public.expenses
    add column if not exists created_by uuid references public.users (id),
    add column if not exists updated_by uuid references public.users (id),
    add column if not exists updated_at timestamptz;

alter table public.settlements
    add column if not exists created_by uuid references public.users (id),
    add column if not exists updated_by uuid references public.users (id),
    add column if not exists updated_at timestamptz;

-- `updated_by` points at `public.users`, which account deletion anonymizes
-- rather than deletes (routers/users.py), so these references stay valid and an
-- edit made by somebody who has since left reads as "Deleted user" -- the same
-- way the expenses they took part in already do.
comment on column public.expenses.updated_by is
    'Last member to change this row, including a soft-delete. NULL means untouched since creation.';
comment on column public.settlements.updated_by is
    'Last member to change this row, including a soft-delete. NULL means untouched since creation.';
