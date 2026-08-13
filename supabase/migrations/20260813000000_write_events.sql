-- Make the write quotas survive a group deletion.
--
-- The quotas in api/_src/ratelimit.py used to count the very rows they were
-- protecting: expenses + settlements for the ledger window, groups for the
-- group-creation window, group_invitations for the three invitation windows.
-- Deleting a group is a HARD delete that takes its expenses, settlements,
-- invitations and members with it (routers/groups.py delete_group), and any
-- member may delete a group once it is settled. So create a group -> fill it
-- -> delete it -> repeat reset every one of those windows, and the brakes only
-- ever stopped clients that were not trying to get around them.
--
-- write_events is the tombstone: one append-only row per quota-consuming
-- write, keyed by the caller, referencing nothing that a group deletion
-- cascades through. The row outlives whatever entry it was charged for.
--
-- Taking the count off the ledger tables also moved the ledger window onto its
-- natural axis. It was per-GROUP, which meant one member could consume the
-- window for everyone else in the group; it is now per-caller, like the
-- group-creation window already was.

CREATE TABLE public.write_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- No ON DELETE CASCADE, deliberately. Account deletion anonymizes the
    -- public.users row rather than deleting it (routers/users.py), so this FK
    -- never fires today -- and a CASCADE here would be a loaded gun aimed at
    -- the whole point of the table if that ever changes.
    user_id UUID NOT NULL REFERENCES public.users(id),
    kind TEXT NOT NULL CHECK (kind IN ('LEDGER', 'GROUP', 'INVITE')),
    -- INVITE rows only: SHA-256 of the lowercased recipient address, never the
    -- address itself. The per-recipient window ("this address cannot be
    -- invited more than N times a day") only ever needs equality matching, and
    -- a hash does that exactly as well -- so a table that deliberately
    -- outlives the invitation it was charged for never holds a contactable
    -- address, and account deletion's promise to anonymize the address
    -- (routers/users.py, and the Privacy Policy in src/lib/legal.ts) survives
    -- intact. Unpeppered on purpose rather than for show: anyone who can read
    -- this column can already read public.users.email in plaintext, so a
    -- pepper would buy nothing here while adding a key to manage and rotate.
    -- These rows are also pruned once they age out of the window.
    recipient_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One index per axis the quotas count on. Together they also serve the
-- opportunistic prune, which is keyed by user_id.
CREATE INDEX idx_write_events_user_created
    ON public.write_events (user_id, created_at);
CREATE INDEX idx_write_events_kind_created
    ON public.write_events (kind, created_at);
CREATE INDEX idx_write_events_recipient
    ON public.write_events (recipient_hash, created_at)
    WHERE recipient_hash IS NOT NULL;

-- Deliberately NOT backfilled from the existing ledger. Nothing records who
-- created an expense or a settlement -- that absence is what this table is
-- fixing -- so a backfill could only attribute writes to the payer, who is
-- frequently not the author. Charging an innocent member for someone else's
-- entries to salvage one 24h window is the worse trade: the cost of skipping
-- it is that rows written in the day before this migration do not count, once.
