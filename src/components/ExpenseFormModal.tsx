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
import { AMOUNT_PATTERN, COMMON_CURRENCIES, normalizeAmountInput } from "../lib/currency";
import { CATEGORY_GROUPS } from "../lib/categories";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../lib/i18n";
import Modal from "./Modal";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";

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
  const { t, tCategory, tCategoryGroup } = useI18n();
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
        if (splitType === "EXACT")
          return { user_id: m.id, amount: normalizeAmountInput(exactAmounts[m.id] || "0") };
        if (splitType === "PERCENTAGE")
          return { user_id: m.id, percentage: normalizeAmountInput(percentages[m.id] || "0") };
        return { user_id: m.id };
      });

  const save = useMutation({
    mutationFn: async () => {
      const payload: ExpensePayload = {
        description: description.trim(),
        category,
        split_type: splitType,
        total_amount: normalizeAmountInput(totalAmount),
        currency,
        paid_by_user_id: paidBy,
        splits: buildSplits(),
      };
      if (expense) {
        return api.patch<Expense>(`/expenses/${expense.id}`, payload);
      }
      return api.post<Expense>(`/groups/${group.id}/expenses`, payload, newIdempotencyKey());
    },
    onSuccess: onSaved,
  });

  const parseNum = (s: string) => parseFloat(normalizeAmountInput(s)) || 0;
  const selected = group.members.filter((m) => participants.has(m.id));
  const exactSum = selected.reduce((acc, m) => acc + parseNum(exactAmounts[m.id] || "0"), 0);
  const pctSum = selected.reduce((acc, m) => acc + parseNum(percentages[m.id] || "0"), 0);

  return (
    <Modal title={expense ? t("editExpense") : t("addExpense")} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="space-y-4"
      >
        <div>
          <label className="mb-1 block text-sm font-medium">{t("description")}</label>
          <input
            autoFocus
            required
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={t("descriptionPlaceholder")}
            className={inputCls}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">{t("amount")}</label>
            <input
              required
              inputMode="decimal"
              pattern={AMOUNT_PATTERN}
              value={totalAmount}
              onChange={(e) => setTotalAmount(e.target.value)}
              placeholder="120,50"
              className={inputCls}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("currency")}</label>
            <select
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
              className={inputCls}
            >
              {COMMON_CURRENCIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium">{t("category")}</label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className={inputCls}
            >
              {CATEGORY_GROUPS.map((g) => (
                <optgroup key={g.group} label={tCategoryGroup(g.group)}>
                  {g.categories.map((c) => (
                    <option key={c.value} value={c.value}>
                      {tCategory(c.value)}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("paidBy")}</label>
            <select value={paidBy} onChange={(e) => setPaidBy(e.target.value)} className={inputCls}>
              {group.members.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.id === myId ? t("you") : (m.full_name ?? m.email)}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">{t("split")}</label>
          <div className="mb-2 flex gap-1 rounded-lg bg-slate-200/60 p-1 dark:bg-slate-800">
            {(
              [
                ["EQUAL", t("splitEqually")],
                ["EXACT", t("splitExact")],
                ["PERCENTAGE", t("splitPercent")],
              ] as const
            ).map(([type, label]) => (
              <button
                key={type}
                type="button"
                onClick={() => setSplitType(type)}
                className={`flex-1 rounded-md px-2 py-1 text-xs font-medium ${
                  splitType === type
                    ? "bg-white shadow-sm dark:bg-slate-700"
                    : "text-slate-600 dark:text-slate-400"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <ul className="max-h-56 space-y-1 overflow-y-auto rounded-lg border border-slate-200 p-2 dark:border-slate-700">
            {group.members.map((m) => (
              <li key={m.id} className="flex items-center justify-between gap-2 px-1 py-1">
                <label className="flex flex-1 cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={participants.has(m.id)}
                    onChange={() => toggleParticipant(m.id)}
                    className="h-4 w-4 accent-teal-600"
                  />
                  {m.id === myId ? t("you") : (m.full_name ?? m.email)}
                </label>
                {splitType === "EXACT" && participants.has(m.id) && (
                  <input
                    inputMode="decimal"
                    pattern={AMOUNT_PATTERN}
                    value={exactAmounts[m.id] ?? ""}
                    onChange={(e) => setExactAmounts({ ...exactAmounts, [m.id]: e.target.value })}
                    placeholder="0,00"
                    className="w-24 rounded-md border border-slate-300 bg-white px-2 py-1 text-right text-sm dark:border-slate-600 dark:bg-slate-800"
                  />
                )}
                {splitType === "PERCENTAGE" && participants.has(m.id) && (
                  <div className="flex items-center gap-1">
                    <input
                      inputMode="decimal"
                      pattern={AMOUNT_PATTERN}
                      value={percentages[m.id] ?? ""}
                      onChange={(e) => setPercentages({ ...percentages, [m.id]: e.target.value })}
                      placeholder="0"
                      className="w-16 rounded-md border border-slate-300 bg-white px-2 py-1 text-right text-sm dark:border-slate-600 dark:bg-slate-800"
                    />
                    <span className="text-xs text-slate-500 dark:text-slate-400">%</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {splitType === "EXACT" && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t("sumOfAmounts")}: {exactSum.toFixed(2)} ({t("mustEqual")}{" "}
              {totalAmount || t("theTotal")})
            </p>
          )}
          {splitType === "PERCENTAGE" && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t("sumOfPercentages")}: {pctSum} ({t("mustBe100")})
            </p>
          )}
        </div>

        {save.error && (
          <p className="text-sm text-red-600 dark:text-red-400">{(save.error as Error).message}</p>
        )}

        <button
          type="submit"
          disabled={save.isPending || participants.size === 0}
          className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {save.isPending ? t("saving") : expense ? t("saveChanges") : t("addExpense")}
        </button>
      </form>
    </Modal>
  );
}
