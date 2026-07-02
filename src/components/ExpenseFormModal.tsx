import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, newIdempotencyKey } from "../lib/api";
import type {
  Expense,
  ExpensePayload,
  GroupDetail,
  SplitInput,
  SplitType,
} from "../lib/types";
import { COMMON_CURRENCIES } from "../lib/currency";
import { CATEGORY_GROUPS } from "../lib/categories";
import { useAuth } from "../hooks/useAuth";
import Modal from "./Modal";

export default function ExpenseFormModal({
  group,
  expense,
  onClose,
  onSaved,
}: {
  group: GroupDetail;
  expense: Expense | null; // null = create
  onClose: () => void;
  onSaved: () => void;
}) {
  const { session } = useAuth();
  const myId = session?.user.id;

  const [description, setDescription] = useState(expense?.description ?? "");
  const [category, setCategory] = useState(expense?.category ?? "General");
  const [totalAmount, setTotalAmount] = useState(expense?.total_amount ?? "");
  const [currency, setCurrency] = useState(expense?.currency ?? "PLN");
  const [paidBy, setPaidBy] = useState(expense?.paid_by_user_id ?? myId ?? "");
  const [splitType, setSplitType] = useState<SplitType>(expense?.split_type ?? "EQUAL");
  const [participants, setParticipants] = useState<Set<string>>(
    new Set(expense ? expense.splits.map((s) => s.user_id) : group.members.map((m) => m.id)),
  );
  const [exactAmounts, setExactAmounts] = useState<Record<string, string>>(
    Object.fromEntries((expense?.splits ?? []).map((s) => [s.user_id, s.owed_amount])),
  );
  const [percentages, setPercentages] = useState<Record<string, string>>({});

  const toggleParticipant = (id: string) => {
    const next = new Set(participants);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setParticipants(next);
  };

  const buildSplits = (): SplitInput[] =>
    group.members
      .filter((m) => participants.has(m.id))
      .map((m) => {
        if (splitType === "EXACT") return { user_id: m.id, amount: exactAmounts[m.id] || "0" };
        if (splitType === "PERCENTAGE")
          return { user_id: m.id, percentage: percentages[m.id] || "0" };
        return { user_id: m.id };
      });

  const save = useMutation({
    mutationFn: async () => {
      const payload: ExpensePayload = {
        description: description.trim(),
        category,
        split_type: splitType,
        total_amount: totalAmount,
        currency,
        paid_by_user_id: paidBy,
        splits: buildSplits(),
      };
      if (expense) {
        return api.patch<Expense>(`/expenses/${expense.id}`, payload);
      }
      return api.post<Expense>(
        `/groups/${group.id}/expenses`,
        payload,
        newIdempotencyKey(),
      );
    },
    onSuccess: onSaved,
  });

  const selected = group.members.filter((m) => participants.has(m.id));
  const exactSum = selected.reduce((acc, m) => acc + (parseFloat(exactAmounts[m.id] || "0") || 0), 0);
  const pctSum = selected.reduce((acc, m) => acc + (parseFloat(percentages[m.id] || "0") || 0), 0);

  return (
    <Modal title={expense ? "Edit expense" : "Add expense"} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="space-y-4"
      >
        <div>
          <label className="mb-1 block text-sm font-medium">Description</label>
          <input
            autoFocus
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Dinner at Nolio"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-500"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Amount</label>
            <input
              required
              inputMode="decimal"
              pattern="^\d+(\.\d+)?$"
              value={totalAmount}
              onChange={(e) => setTotalAmount(e.target.value)}
              placeholder="120.50"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Currency</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {COMMON_CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">Category</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {CATEGORY_GROUPS.map((g) => (
                <optgroup key={g.group} label={g.group}>
                  {g.categories.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.value}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">Paid by</label>
            <select
              value={paidBy}
              onChange={(e) => setPaidBy(e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500"
            >
              {group.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id === myId ? "You" : (m.full_name ?? m.email)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">Split</label>
          <div className="mb-2 flex gap-1 rounded-lg bg-slate-200/60 p-1">
            {(["EQUAL", "EXACT", "PERCENTAGE"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setSplitType(t)}
                className={`flex-1 rounded-md px-2 py-1 text-xs font-medium ${
                  splitType === t ? "bg-white shadow-sm" : "text-slate-600"
                }`}
              >
                {t === "EQUAL" ? "Equally" : t === "EXACT" ? "Exact amounts" : "Percentages"}
              </button>
            ))}
          </div>

          <ul className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
            {group.members.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 px-1 py-1">
                <label className="flex flex-1 cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={participants.has(m.id)}
                    onChange={() => toggleParticipant(m.id)}
                    className="h-4 w-4 accent-teal-600"
                  />
                  {m.id === myId ? "You" : (m.full_name ?? m.email)}
                </label>
                {splitType === "EXACT" && participants.has(m.id) && (
                  <input
                    inputMode="decimal"
                    value={exactAmounts[m.id] ?? ""}
                    onChange={(e) =>
                      setExactAmounts({ ...exactAmounts, [m.id]: e.target.value })
                    }
                    placeholder="0.00"
                    className="w-24 rounded-md border border-slate-300 px-2 py-1 text-right text-sm"
                  />
                )}
                {splitType === "PERCENTAGE" && participants.has(m.id) && (
                  <div className="flex items-center gap-1">
                    <input
                      inputMode="decimal"
                      value={percentages[m.id] ?? ""}
                      onChange={(e) =>
                        setPercentages({ ...percentages, [m.id]: e.target.value })
                      }
                      placeholder="0"
                      className="w-16 rounded-md border border-slate-300 px-2 py-1 text-right text-sm"
                    />
                    <span className="text-xs text-slate-500">%</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {splitType === "EXACT" && (
            <p className="mt-1 text-xs text-slate-500">
              Sum of amounts: {exactSum.toFixed(2)} (must equal {totalAmount || "the total"})
            </p>
          )}
          {splitType === "PERCENTAGE" && (
            <p className="mt-1 text-xs text-slate-500">Sum of percentages: {pctSum} (must be 100)</p>
          )}
        </div>

        {save.error && <p className="text-sm text-red-600">{(save.error as Error).message}</p>}

        <button
          type="submit"
          disabled={save.isPending || participants.size === 0}
          className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {save.isPending ? "Saving…" : expense ? "Save changes" : "Add expense"}
        </button>
      </form>
    </Modal>
  );
}
