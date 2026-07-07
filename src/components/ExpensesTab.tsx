import { useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Expense, ExpenseList, GroupDetail } from "../lib/types";
import { formatMoney } from "../lib/currency";
import { formatDateOnly } from "../lib/dates";
import { CategoryIcon } from "../lib/categories";
import { expensesQuery, PAGE_SIZE } from "../lib/queries";
import { useI18n } from "../lib/i18n";
import ExpenseFormModal from "./ExpenseFormModal";
import ConfirmDialog from "./ConfirmDialog";
import ListSkeleton from "./ListSkeleton";

export default function ExpensesTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const { t, tCategory, dateLocale } = useI18n();
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [adding, setAdding] = useState(false);
  const [deleting, setDeleting] = useState<Expense | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? t("formerMember");

  const { data, isLoading, error } = useQuery({
    ...expensesQuery(group.id, offset),
    // Keep showing the current page while the next one loads.
    placeholderData: keepPreviousData,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["expenses", group.id] });
    queryClient.invalidateQueries({ queryKey: ["balances", group.id] });
  };

  const deleteExpense = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/expenses/${id}`),
    // Optimistic: the row disappears immediately; restored if the server says no.
    onMutate: async (id: string) => {
      setDeleting(null);
      await queryClient.cancelQueries({ queryKey: ["expenses", group.id] });
      const previous = queryClient.getQueriesData<ExpenseList>({
        queryKey: ["expenses", group.id],
      });
      queryClient.setQueriesData<ExpenseList>(
        { queryKey: ["expenses", group.id] },
        (old) => (old ? { ...old, items: old.items.filter((e) => e.id !== id) } : old),
      );
      return { previous };
    },
    onError: (_err, _id, ctx) => {
      ctx?.previous.forEach(([key, value]) => queryClient.setQueryData(key, value));
    },
    onSettled: invalidate,
  });

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> {t("addExpense")}
        </button>
      </div>

      {isLoading && <ListSkeleton rows={4} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}
      {deleteExpense.error && (
        <p className="mb-2 text-sm text-red-600 dark:text-red-400">
          {(deleteExpense.error as Error).message}
        </p>
      )}

      {data && data.items.length === 0 && offset === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          {t("noExpenses")}
        </div>
      )}

      <ul className="space-y-2">
        {data?.items.map((e) => (
          <li
            key={e.id}
            className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                <CategoryIcon category={e.category} className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="truncate font-medium">{e.description}</div>
                <div className="truncate text-xs text-slate-500 dark:text-slate-400">
                  {nameOf(e.paid_by_user_id)} {t("paidVerb")} · {tCategory(e.category)} ·{" "}
                  {formatDateOnly(e.expense_date, dateLocale)}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <span className="mr-2 font-semibold">{formatMoney(e.total_amount, e.currency)}</span>
              <button
                onClick={() => setEditing(e)}
                className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                title={t("edit")}
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => setDeleting(e)}
                className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                title={t("delete")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </li>
        ))}
      </ul>

      {data && (data.items.length === PAGE_SIZE || offset > 0) && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40 dark:border-slate-600 dark:bg-slate-900"
          >
            <ChevronLeft className="h-4 w-4" /> {t("newer")}
          </button>
          <span className="text-slate-500 dark:text-slate-400">
            {offset + 1}–{offset + data.items.length}
          </span>
          <button
            disabled={data.items.length < PAGE_SIZE}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40 dark:border-slate-600 dark:bg-slate-900"
          >
            {t("older")} <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {(adding || editing) && (
        <ExpenseFormModal
          group={group}
          expense={editing}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onSaved={() => {
            setAdding(false);
            setEditing(null);
            invalidate();
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title={t("deleteExpenseTitle")}
          message={`„${deleting.description}” — ${t("deleteExpenseMsg")}`}
          busy={deleteExpense.isPending}
          onConfirm={() => deleteExpense.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
