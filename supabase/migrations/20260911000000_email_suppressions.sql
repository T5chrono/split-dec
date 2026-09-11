-- Recipient-controlled opt-out from invitation email (api/_src/unsubscribe.py).
--
-- One row per address that has asked not to hear from us, keyed by the same
-- unpeppered SHA-256 that write_events uses. No address, no account link, no
-- other column: the table only ever answers "has this one objected?".
--
-- Unlike write_events these rows are never pruned. A tombstone there expires
-- with the window it feeds; an objection here stands until it is withdrawn,
-- and forgetting it would mean resuming mail to someone who refused it.

create table if not exists public.email_suppressions (
    recipient_hash text primary key,
    created_at timestamptz not null default now()
);

-- The app connects as splitdec_app (20260904100000), which holds no privileges
-- it was not handed. A new table without this is `permission denied` in
-- production and nowhere else -- the SQLite suite builds its schema from the
-- models and has no roles at all. tests/test_grants_pg.py checks both
-- directions against the live catalogs.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'splitdec_app') then
        grant select, insert, update, delete on public.email_suppressions to splitdec_app;
    end if;
end
$$;
