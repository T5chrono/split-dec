import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Expense, ExpenseList, GroupDetail } from "../lib/types";
import { formatMoney } from "../lib/currency";
import { CategoryIcon } from "../lib/categories";
import ExpenseFormModal from "./ExpenseFormModal";

const PAGE_SIZE = 20;

export default function ExpensesTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<Expense | null>(null);
  const [adding, setAdding] = useState(false);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? "Former member";

  const { data, isLoading, error } = useQuery({
    queryKey: ["expenses", group.id, offset],
    queryFn: () =>
      api.get<ExpenseList>(`/groups/${group.id}/expenses?limit=${PAGE_SIZE}&offset=${offset}`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["expenses", group.id] });
    queryClient.invalidateQueries({ queryKey: ["balances", group.id] });
  };

  const deleteExpense = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/expenses/${id}`),
    onSuccess: invalidate,
  });

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> Add expense
        </button>
      </div>

      {isLoading && <p className="text-slate-500">Loading expenses…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {deleteExpense.error && (
        <p className="mb-2 text-sm text-red-600">{(deleteExpense.error as Error).message}</p>
      )}

      {data && data.items.length === 0 && offset === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          No expenses yet. Add the first one!
        </div>
      )}

      <ul className="space-y-2">
        {data?.items.map((e) => (
          <li
            key={e.id}
            className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
          >
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-600">
                <CategoryIcon category={e.category} className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="truncate font-medium">{e.description}</div>
                <div className="truncate text-xs text-slate-500">
                  {nameOf(e.paid_by_user_id)} paid · {e.category} ·{" "}
                  {new Date(e.created_at).toLocaleDateString()}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <span className="mr-2 font-semibold">{formatMoney(e.total_amount, e.currency)}</span>
              <button
                onClick={() => setEditing(e)}
                className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                title="Edit"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => deleteExpense.mutate(e.id)}
                className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                title="Delete"
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
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            <ChevronLeft className="h-4 w-4" /> Newer
          </button>
          <span className="text-slate-500">
            {offset + 1}–{offset + data.items.length}
          </span>
          <button
            disabled={data.items.length < PAGE_SIZE}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 disabled:opacity-40"
          >
            Older <ChevronRight className="h-4 w-4" />
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
    </div>
  );
}
