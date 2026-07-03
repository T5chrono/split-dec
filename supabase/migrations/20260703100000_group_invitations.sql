-- Group membership becomes invitation-based: the invitee must accept.
-- Invitations are keyed by (lowercased) email so people who are not on
-- SplitDec yet see their pending invitations after they first sign up.

CREATE TABLE public.group_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    invited_by UUID NOT NULL REFERENCES public.users(id),
    invited_user_id UUID REFERENCES public.users(id),
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACCEPTED', 'DECLINED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at TIMESTAMPTZ
);

-- One live invitation per (group, email).
CREATE UNIQUE INDEX uq_group_invitations_pending
    ON public.group_invitations (group_id, email) WHERE status = 'PENDING';
CREATE INDEX idx_group_invitations_email
    ON public.group_invitations (email) WHERE status = 'PENDING';
CREATE INDEX idx_group_invitations_user
    ON public.group_invitations (invited_user_id) WHERE status = 'PENDING';
