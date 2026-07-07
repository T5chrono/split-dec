import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, HandCoins, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { GroupDetail, Settlement } from "../lib/types";
import { settlementsQuery } from "../lib/queries";
import { formatMoney } from "../lib/currency";
import { useI18n } from "../lib/i18n";
import SettleUpModal from "./SettleUpModal";
import ConfirmDialog from "./ConfirmDialog";
import Spinner from "./Spinner";

export default function SettlementsTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const { t, dateLocale } = useI18n();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Settlement | null>(null);
  const [deleting, setDeleting] = useState<Settlement | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? t("formerMember");

  const { data, isLoading, error } = useQuery(settlementsQuery(group.id));

  const deleteSettlement = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/settlements/${id}`),
    // Optimistic: the row disappears immediately; restored if the server says no.
    onMutate: async (id: string) => {
      setDeleting(null);
      await queryClient.cancelQueries({ queryKey: ["settlements", group.id] });
      const previous = queryClient.getQueryData<Settlement[]>(["settlements", group.id]);
      queryClient.setQueryData<Settlement[]>(
        ["settlements", group.id],
        (old) => old?.filter((s) => s.id !== id),
      );
      return { previous };
    },
    onError: (_err, _id, ctx) => {
      queryClient.setQueryData(["settlements", group.id], ctx?.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["settlements", group.id] });
      queryClient.invalidateQueries({ queryKey: ["balances", group.id] });
    },
  });

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setAdding(true)}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> {t("recordPayment")}
        </button>
      </div>

      {isLoading && <Spinner label={t("loadingSettlements")} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}
      {deleteSettlement.error && (
        <p className="mb-2 text-sm text-red-600 dark:text-red-400">
          {(deleteSettlement.error as Error).message}
        </p>
      )}

      {data && data.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          <HandCoins className="mx-auto mb-3 h-8 w-8 text-slate-400 dark:text-slate-500" />
          {t("noPayments")}
        </div>
      )}

      <ul className="space-y-2">
        {data?.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">{nameOf(s.paid_by_user_id)}</span>
              <ArrowRight className="h-4 w-4 text-slate-400" />
              <span className="font-medium">{nameOf(s.paid_to_user_id)}</span>
              <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                {new Date(s.created_at).toLocaleDateString(dateLocale)}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="mr-2 font-semibold text-emerald-700 dark:text-emerald-400">
                {formatMoney(s.amount, s.currency)}
              </span>
              <button
                onClick={() => setEditing(s)}
                className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-300"
                title={t("edit")}
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => setDeleting(s)}
                className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                title={t("delete")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </li>
        ))}
      </ul>

      {adding && <SettleUpModal group={group} onClose={() => setAdding(false)} />}
      {editing && (
        <SettleUpModal group={group} editing={editing} onClose={() => setEditing(null)} />
      )}
      {deleting && (
        <ConfirmDialog
          title={t("deleteSettlementTitle")}
          message={`${nameOf(deleting.paid_by_user_id)} → ${nameOf(deleting.paid_to_user_id)}, ${formatMoney(deleting.amount, deleting.currency)} — ${t("deleteSettlementMsg")}`}
          busy={deleteSettlement.isPending}
          onConfirm={() => deleteSettlement.mutate(deleting.id)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
