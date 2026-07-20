-- Cancelling an invitation used to DELETE the row, which made the send
-- quotas in the API (per-inviter / per-recipient / global, 24h windows)
-- trivially resettable: invite, cancel, repeat, and the same address can be
-- emailed forever. Cancellation now marks the row instead, so it still
-- counts. The partial unique index below already only covers PENDING rows,
-- so a cancelled invitation does not block re-inviting the same address.

ALTER TABLE public.group_invitations
    DROP CONSTRAINT group_invitations_status_check;

ALTER TABLE public.group_invitations
    ADD CONSTRAINT group_invitations_status_check
    CHECK (status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'CANCELLED'));

-- The quota query counts rows inside a rolling 24h window across the whole
-- table; keep it off a sequential scan as invitation history accumulates.
CREATE INDEX IF NOT EXISTS idx_group_invitations_created_at
    ON public.group_invitations (created_at);
