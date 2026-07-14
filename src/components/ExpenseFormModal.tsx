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
import { Trash2 } from "lucide-react";
import {
  AMOUNT_PATTERN,
  COMMON_CURRENCIES,
  fromMinorUnits,
  normalizeAmountInput,
  toMinorUnits,
  trimAmount,
} from "../lib/currency";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../lib/i18n";
import { todayLocalISO } from "../lib/dates";
import Modal from "./Modal";
import DatePicker from "./DatePicker";
import CategorySelect from "./CategorySelect";

const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";

/** Initial percentage fields when editing a PERCENTAGE expense: derived from
 *  the stored owed amounts — all but the last, which the autofill
 *  reconstructs so the total is exactly 100 despite rounding. Money strings
 *  never pass through floats: both amounts have exactly 4 decimals from the
 *  API, so stripping the dot yields exact integer minor units. */
function derivePercentages(expense: Expense): Record<string, string> {
  if (expense.split_type !== "PERCENTAGE") return {};
  const toUnits = (s: string) => BigInt(s.replace(".", ""));
  const total = toUnits(expense.total_amount);
  return Object.fromEntries(
    expense.splits.slice(0, -1).map((s) => {
      // Percentage in hundredths, rounded half-up: owed / total * 100_00
      const hundredths = (toUnits(s.owed_amount) * 10000n + total / 2n) / total;
      return [s.user_id, String(Number(hundredths) / 100)];
    }),
  );
}

export default function ExpenseFormModal({
  group,
  expense,
  onClose,
  onSaved,
  onDelete,
}: {
  group: GroupDetail;
  expense: Expense | null; // null = create
  onClose: () => void;
  onSaved: () => void;
  onDelete?: () => void; // present only when editing
}) {
  const { session } = useAuth();
  const { t } = useI18n();
  const myId = session?.user.id;

  const [description, setDescription] = useState(expense?.description ?? "");
  const [category, setCategory] = useState(expense?.category ?? "General");
  const [totalAmount, setTotalAmount] = useState(
    expense ? trimAmount(expense.total_amount, expense.currency) : "",
  );
  const [currency, setCurrency] = useState(expense?.currency ?? "PLN");
  const [paidBy, setPaidBy] = useState(expense?.paid_by_user_id ?? myId ?? "");
  const [expenseDate, setExpenseDate] = useState(
    expense?.expense_date ?? todayLocalISO(),
  );
  const [splitType, setSplitType] = useState<SplitType>(expense?.split_type ?? "EQUAL");
  const [participants, setParticipants] = useState<Set<string>>(
    new Set(expense ? expense.splits.map((s) => s.user_id) : group.members.map((m) => m.id)),
  );
  const [exactAmounts, setExactAmounts] = useState<Record<string, string>>(
    Object.fromEntries(
      (expense?.splits ?? []).map((s) => [
        s.user_id,
        trimAmount(s.owed_amount, expense?.currency ?? "PLN"),
      ]),
    ),
  );
  const [percentages, setPercentages] = useState<Record<string, string>>(() =>
    expense ? derivePercentages(expense) : {},
  );

  const toggleParticipant = (id: string) => {
    const next = new Set(participants);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setParticipants(next);
  };

  const parseNum = (s: string) => parseFloat(normalizeAmountInput(s)) || 0;
  const selected = group.members.filter((m) => participants.has(m.id));

  // Percentage autofill: when exactly one selected member has no percentage,
  // it is obviously 100 minus the rest — fill it in automatically.
  const emptyPctIds = selected
    .map((m) => m.id)
    .filter((id) => !(percentages[id] ?? "").trim());
  const filledPctSum =
    Math.round(
      selected.reduce((acc, m) => acc + parseNum(percentages[m.id] ?? ""), 0) * 100,
    ) / 100;
  const autoPct =
    splitType === "PERCENTAGE" && emptyPctIds.length === 1 && 100 - filledPctSum > 0
      ? Math.round((100 - filledPctSum) * 100) / 100
      : null;

  // Same idea for EXACT amounts: one empty field gets total minus the rest.
  // Integer minor-unit math (no floats); disabled while any filled entry or
  // the total is unparseable.
  const emptyExactIds = selected
    .map((m) => m.id)
    .filter((id) => !(exactAmounts[id] ?? "").trim());
  const totalUnits = toMinorUnits(totalAmount, currency);
  const filledExactUnits = selected
    .filter((m) => (exactAmounts[m.id] ?? "").trim())
    .map((m) => toMinorUnits(exactAmounts[m.id], currency));
  const filledExactSum = filledExactUnits.every((u): u is number => u !== null)
    ? filledExactUnits.reduce((a: number, b) => a + (b as number), 0)
    : null;
  const autoExact =
    splitType === "EXACT" &&
    emptyExactIds.length === 1 &&
    totalUnits !== null &&
    filledExactSum !== null &&
    totalUnits - filledExactSum > 0
      ? fromMinorUnits(totalUnits - filledExactSum, currency)
      : null;

  const buildSplits = (): SplitInput[] =>
    selected.map((m) => {
      if (splitType === "EXACT") {
        const raw = (exactAmounts[m.id] ?? "").trim();
        const amount =
          raw !== ""
            ? normalizeAmountInput(raw)
            : autoExact !== null && emptyExactIds[0] === m.id
              ? autoExact
              : "0";
        return { user_id: m.id, amount };
      }
      if (splitType === "PERCENTAGE") {
        const raw = (percentages[m.id] ?? "").trim();
        const pct =
          raw !== ""
            ? normalizeAmountInput(raw)
            : autoPct !== null && emptyPctIds[0] === m.id
              ? String(autoPct)
              : "0";
        return { user_id: m.id, percentage: pct };
      }
      return { user_id: m.id };
    });

  // True when none of the financial inputs differ from the expense being
  // edited. Matters for PERCENTAGE splits especially: the form's percentages
  // are *reconstructed* (rounded) from stored owed amounts, so resubmitting
  // them on a metadata-only edit could silently shift money between members.
  const financialsUnchanged = (): boolean => {
    if (!expense) return false;
    if (
      splitType !== expense.split_type ||
      currency !== expense.currency ||
      paidBy !== expense.paid_by_user_id ||
      normalizeAmountInput(totalAmount) !== trimAmount(expense.total_amount, expense.currency)
    ) {
      return false;
    }
    const initialIds = new Set(expense.splits.map((s) => s.user_id));
    if (participants.size !== initialIds.size) return false;
    for (const id of participants) if (!initialIds.has(id)) return false;
    if (splitType === "EXACT") {
      return expense.splits.every(
        (s) =>
          normalizeAmountInput(exactAmounts[s.user_id] ?? "") ===
          trimAmount(s.owed_amount, expense.currency),
      );
    }
    if (splitType === "PERCENTAGE") {
      const initial = derivePercentages(expense);
      return [...participants].every(
        (id) => (percentages[id] ?? "").trim() === (initial[id] ?? ""),
      );
    }
    return true; // EQUAL with same participants and total
  };

  const save = useMutation({
    mutationFn: async () => {
      if (expense && financialsUnchanged()) {
        // Metadata-only PATCH: the backend leaves splits untouched, so a
        // description/category/date edit can never move money.
        return api.patch<Expense>(`/expenses/${expense.id}`, {
          description: description.trim(),
          category,
          expense_date: expenseDate,
        });
      }
      const payload: ExpensePayload = {
        description: description.trim(),
        category,
        split_type: splitType,
        total_amount: normalizeAmountInput(totalAmount),
        currency,
        paid_by_user_id: paidBy,
        expense_date: expenseDate,
        splits: buildSplits(),
      };
      if (expense) {
        return api.patch<Expense>(`/expenses/${expense.id}`, payload);
      }
      return api.post<Expense>(`/groups/${group.id}/expenses`, payload, newIdempotencyKey());
    },
    onSuccess: onSaved,
  });

  const exactSum =
    filledExactSum !== null
      ? fromMinorUnits(
          filledExactSum + (autoExact !== null ? toMinorUnits(autoExact, currency)! : 0),
          currency,
        )
      : selected.reduce((acc, m) => acc + parseNum(exactAmounts[m.id] || "0"), 0).toFixed(2);
  const pctSum = Math.round((filledPctSum + (autoPct ?? 0)) * 100) / 100;

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

        <div>
          <label className="mb-1 block text-sm font-medium">{t("date")}</label>
          <DatePicker value={expenseDate} onChange={setExpenseDate} />
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
            <CategorySelect value={category} onChange={setCategory} />
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
                    placeholder={
                      autoExact !== null && emptyExactIds[0] === m.id ? autoExact : "0,00"
                    }
                    className={`w-24 rounded-md border px-2 py-1 text-right text-sm dark:bg-slate-800 ${
                      autoExact !== null && emptyExactIds[0] === m.id
                        ? "border-teal-400 placeholder:text-teal-600 dark:border-teal-600 dark:placeholder:text-teal-400"
                        : "border-slate-300 bg-white dark:border-slate-600"
                    }`}
                  />
                )}
                {splitType === "PERCENTAGE" && participants.has(m.id) && (
                  <div className="flex items-center gap-1">
                    <input
                      inputMode="decimal"
                      pattern={AMOUNT_PATTERN}
                      value={percentages[m.id] ?? ""}
                      onChange={(e) => setPercentages({ ...percentages, [m.id]: e.target.value })}
                      placeholder={
                        autoPct !== null && emptyPctIds[0] === m.id ? String(autoPct) : "0"
                      }
                      className={`w-16 rounded-md border px-2 py-1 text-right text-sm dark:bg-slate-800 ${
                        autoPct !== null && emptyPctIds[0] === m.id
                          ? "border-teal-400 placeholder:text-teal-600 dark:border-teal-600 dark:placeholder:text-teal-400"
                          : "border-slate-300 bg-white dark:border-slate-600"
                      }`}
                    />
                    <span className="text-xs text-slate-500 dark:text-slate-400">%</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
          {splitType === "EXACT" && (
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              {t("sumOfAmounts")}: {exactSum} ({t("mustEqual")}{" "}
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

        {expense && onDelete && (
          <button
            type="button"
            onClick={onDelete}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            <Trash2 className="h-4 w-4" /> {t("deleteExpense")}
          </button>
        )}
      </form>
    </Modal>
  );
}
