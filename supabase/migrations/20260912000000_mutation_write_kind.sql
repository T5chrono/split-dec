-- A fourth kind of quota slot: MUTATION, for editing and withdrawing ledger
-- rows (api/_src/ratelimit.py).
--
-- The creation caps brake how many expenses and settlements one account can
-- *add*. Editing them was unbounded, and an edit is not cheap: it revalidates
-- the participants, recomputes every split, and re-reads the group's balances.
-- So a caller who had spent their 100 creates could still sit in a loop
-- rewriting one expense for as long as they liked.
--
-- The only schema change this needs is the CHECK constraint from
-- 20260813000000, which enumerates the allowed kinds. Dropped and recreated
-- rather than altered, because Postgres has no ALTER ... CHECK: the old
-- constraint has to go before the new one can name the same rows.
--
-- No grant: splitdec_app already holds DML on write_events, and this adds no
-- object. No backfill either -- the rows this kind counts do not exist yet.

alter table public.write_events
    drop constraint if exists write_events_kind_check;

alter table public.write_events
    add constraint write_events_kind_check
    check (kind in ('LEDGER', 'GROUP', 'INVITE', 'MUTATION'));
