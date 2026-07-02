export type SplitType = "EQUAL" | "EXACT" | "PERCENTAGE";

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
}

export interface Group {
  id: string;
  name: string;
  created_by: string;
  created_at: string;
}

export interface GroupDetail extends Group {
  members: User[];
}

export interface ExpenseSplit {
  user_id: string;
  owed_amount: string; // monetary amounts are serialized as strings
}

export interface Expense {
  id: string;
  group_id: string;
  description: string;
  category: string;
  split_type: SplitType;
  total_amount: string;
  currency: string;
  paid_by_user_id: string;
  created_at: string;
  splits: ExpenseSplit[];
}

export interface ExpenseList {
  items: Expense[];
  limit: number;
  offset: number;
}

export interface Settlement {
  id: string;
  group_id: string;
  paid_by_user_id: string;
  paid_to_user_id: string;
  amount: string;
  currency: string;
  created_at: string;
}

export interface BalanceTransfer {
  from_user_id: string;
  to_user_id: string;
  amount: string;
}

export type Balances = Record<string, BalanceTransfer[]>;

export interface SplitInput {
  user_id: string;
  amount?: string;
  percentage?: string;
}

export interface ExpensePayload {
  description: string;
  category: string;
  split_type: SplitType;
  total_amount: string;
  currency: string;
  paid_by_user_id: string;
  splits: SplitInput[];
}

export interface SettlementPayload {
  paid_by_user_id: string;
  paid_to_user_id: string;
  amount: string;
  currency: string;
}
