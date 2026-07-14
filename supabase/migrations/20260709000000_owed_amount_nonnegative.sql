-- Defense-in-depth for split integrity: the API now rejects negative split
-- amounts/percentages; this constraint guarantees it at the storage layer
-- (a negative owed_amount would let balances be manipulated while the
-- sum-equals-total check still passes). Verified no existing rows violate it.

ALTER TABLE public.expense_splits
  ADD CONSTRAINT expense_splits_owed_amount_nonnegative CHECK (owed_amount >= 0);
