import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, HandCoins, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { GroupDetail, Settlement } from "../lib/types";
import { formatMoney } from "../lib/currency";
import SettleUpModal from "./SettleUpModal";

export default function SettlementsTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Settlement | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? "Former member";

  const { data, isLoading, error } = useQuery({
    queryKey: ["settlements", group.id],
    queryFn: () => api.get<Settlement[]>(`/groups/${group.id}/settlements`),
  });

  const deleteSettlement = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/settlements/${id}`),
    onSuccess: () => {
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
          <Plus className="h-4 w-4" /> Record payment
        </button>
      </div>

      {isLoading && <p className="text-slate-500">Loading settlements…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {deleteSettlement.error && (
        <p className="mb-2 text-sm text-red-600">{(deleteSettlement.error as Error).message}</p>
      )}

      {data && data.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <HandCoins className="mx-auto mb-3 h-8 w-8 text-slate-400" />
          No payments recorded yet.
        </div>
      )}

      <ul className="space-y-2">
        {data?.map((s) => (
          <li
            key={s.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
          >
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">{nameOf(s.paid_by_user_id)}</span>
              <ArrowRight className="h-4 w-4 text-slate-400" />
              <span className="font-medium">{nameOf(s.paid_to_user_id)}</span>
              <span className="ml-2 text-xs text-slate-500">
                {new Date(s.created_at).toLocaleDateString()}
              </span>
            </div>
            <div className="flex items-center gap-1">
              <span className="mr-2 font-semibold text-emerald-700">
                {formatMoney(s.amount, s.currency)}
              </span>
              <button
                onClick={() => setEditing(s)}
                className="rounded-md p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                title="Edit"
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                onClick={() => deleteSettlement.mutate(s.id)}
                className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
                title="Delete"
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
    </div>
  );
}
