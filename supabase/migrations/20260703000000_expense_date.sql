-- Expenses carry the date they occurred (user-editable), distinct from the
-- created_at bookkeeping timestamp. Existing rows backfill from created_at.

ALTER TABLE public.expenses
  ADD COLUMN expense_date DATE NOT NULL DEFAULT CURRENT_DATE;

UPDATE public.expenses
  SET expense_date = (created_at AT TIME ZONE 'utc')::date;

-- Listing is ordered by occurrence date (newest first).
CREATE INDEX idx_expenses_group_date ON public.expenses (group_id, expense_date DESC);
