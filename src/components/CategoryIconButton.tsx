import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { Expense, ExpenseList } from "../lib/types";
import { CategoryIcon } from "../lib/categories";
import { useI18n } from "../lib/i18n";
import { CategoryOptions } from "./CategorySelect";

/** The expense-row category icon: click to change the category in place,
 *  without opening the edit view. Uses the partial PATCH (category only)
 *  and updates the list optimistically. */
export default function CategoryIconButton({
  expense,
  groupId,
}: {
  expense: Expense;
  groupId: string;
}) {
  const queryClient = useQueryClient();
  const { t, tCategory } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  useEffect(() => {
    if (open && listRef.current) listRef.current.scrollTop = 0;
  }, [open]);

  const changeCategory = useMutation({
    mutationFn: (category: string) =>
      api.patch<Expense>(`/expenses/${expense.id}`, { category }),
    onMutate: async (category: string) => {
      await queryClient.cancelQueries({ queryKey: ["expenses", groupId] });
      const previous = queryClient.getQueriesData<ExpenseList>({
        queryKey: ["expenses", groupId],
      });
      queryClient.setQueriesData<ExpenseList>({ queryKey: ["expenses", groupId] }, (old) =>
        old
          ? {
              ...old,
              items: old.items.map((e) =>
                e.id === expense.id ? { ...e, category } : e,
              ),
            }
          : old,
      );
      return { previous };
    },
    onError: (_err, _category, ctx) => {
      ctx?.previous.forEach(([key, value]) => queryClient.setQueryData(key, value));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["expenses", groupId] }),
  });

  return (
    <div className="relative shrink-0" ref={ref} onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={`${t("category")}: ${tCategory(expense.category)}`}
        className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100 text-slate-600 transition hover:bg-teal-50 hover:text-teal-600 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700 dark:hover:text-teal-400"
      >
        <CategoryIcon category={expense.category} className="h-6 w-6" />
      </button>

      {open && (
        <div
          role="listbox"
          ref={listRef}
          className="absolute left-0 top-full z-20 mt-2 max-h-72 w-64 overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40"
        >
          <CategoryOptions
            value={expense.category}
            onSelect={(category) => {
              setOpen(false);
              if (category !== expense.category) changeCategory.mutate(category);
            }}
          />
        </div>
      )}
    </div>
  );
}
