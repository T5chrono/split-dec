-- SplitDec initial schema
-- RLS intentionally stays DISABLED on all public tables: the FastAPI backend
-- (connecting via a trusted role) is the sole authorization boundary (spec §1).

CREATE TABLE public.users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    full_name TEXT,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_by UUID NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.group_members (
    group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, user_id)
);

CREATE TABLE public.expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    category TEXT NOT NULL,
    split_type TEXT NOT NULL CHECK (split_type IN ('EQUAL', 'EXACT', 'PERCENTAGE')),
    total_amount NUMERIC(14, 4) NOT NULL CHECK (total_amount > 0),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    paid_by_user_id UUID NOT NULL REFERENCES public.users(id),
    idempotency_key UUID NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE public.expense_splits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_id UUID NOT NULL REFERENCES public.expenses(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES public.users(id),
    owed_amount NUMERIC(14, 4) NOT NULL,
    UNIQUE (expense_id, user_id)
);

CREATE TABLE public.settlements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    paid_by_user_id UUID NOT NULL REFERENCES public.users(id),
    paid_to_user_id UUID NOT NULL REFERENCES public.users(id),
    amount NUMERIC(14, 4) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    idempotency_key UUID NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Indexes (spec §2.3)
CREATE INDEX idx_expenses_group_deleted ON public.expenses (group_id, deleted_at);
CREATE INDEX idx_expense_splits_user ON public.expense_splits (user_id);
CREATE INDEX idx_expense_splits_expense ON public.expense_splits (expense_id);
CREATE INDEX idx_settlements_group ON public.settlements (group_id, deleted_at);
CREATE INDEX idx_group_members_user ON public.group_members (user_id);

-- Auth sync trigger (spec §2.1): copy new auth.users rows into public.users.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.users (id, email, full_name, avatar_url, created_at)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
    COALESCE(NEW.raw_user_meta_data->>'avatar_url', NEW.raw_user_meta_data->>'picture'),
    NOW()
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
