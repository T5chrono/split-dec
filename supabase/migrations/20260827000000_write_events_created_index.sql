-- Index the axis the write_events sweep actually scans.
--
-- The opportunistic prune in api/_src/ratelimit.py used to be scoped to the
-- caller, which the (user_id, created_at) index already served. It is now
-- deployment-wide -- `WHERE created_at < cutoff`, with SKIP LOCKED and a
-- bounded batch -- because rows that outlive the account they were charged to
-- have to be retired by somebody. Account deletion keeps the INVITE
-- tombstones: two of the three invitation windows count a shared resource (the
-- sending domain's reputation, and one address's share of it), so clearing
-- them on deletion handed back allowance that had been spent, and made "sign
-- up, invite, delete, repeat" an unbounded send loop. Nobody sweeps them under
-- the old scoping, since that account never writes again.
--
-- Neither existing index answers `created_at < x` on its own: the leading
-- column is user_id in one and kind in the other. Without this the sweep is a
-- sequential scan on every quota-consuming write, which is affordable at
-- today's volume and would quietly stop being so.

CREATE INDEX idx_write_events_created ON public.write_events (created_at);
