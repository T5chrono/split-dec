import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, HandCoins, Scale } from "lucide-react";
import { api } from "../lib/api";
import type { Balances, GroupDetail, SettlementPayload } from "../lib/types";
import { formatMoney } from "../lib/currency";
import Avatar from "./Avatar";
import SettleUpModal from "./SettleUpModal";

export default function BalancesTab({ group }: { group: GroupDetail }) {
  const [settling, setSettling] = useState<SettlementPayload | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? "Former member";

  const { data, isLoading, error } = useQuery({
    queryKey: ["balances", group.id],
    queryFn: () => api.get<Balances>(`/groups/${group.id}/balances`),
  });

  const entries = Object.entries(data ?? {});
  const allSettled = entries.every(([, transfers]) => transfers.length === 0);

  return (
    <div className="space-y-5">
      {isLoading && <p className="text-slate-500">Computing balances…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}

      {data && allSettled && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <Scale className="mx-auto mb-3 h-8 w-8 text-slate-400" />
          All settled up — nobody owes anything.
        </div>
      )}

      {entries.map(([currency, transfers]) =>
        transfers.length === 0 ? null : (
          <div key={currency}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
              {currency}
            </h3>
            <ul className="space-y-2">
              {transfers.map((t, i) => {
                const from = membersById.get(t.from_user_id);
                const to = membersById.get(t.to_user_id);
                return (
                  <li
                    key={`${currency}-${i}`}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="flex items-center gap-2 text-sm">
                      {from && <Avatar user={from} size={6} />}
                      <span className="font-medium">{nameOf(t.from_user_id)}</span>
                      <ArrowRight className="h-4 w-4 text-slate-400" />
                      {to && <Avatar user={to} size={6} />}
                      <span className="font-medium">{nameOf(t.to_user_id)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-red-600">
                        {formatMoney(t.amount, currency)}
                      </span>
                      <button
                        onClick={() =>
                          setSettling({
                            paid_by_user_id: t.from_user_id,
                            paid_to_user_id: t.to_user_id,
                            amount: t.amount,
                            currency,
                          })
                        }
                        className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700"
                      >
                        <HandCoins className="h-4 w-4" /> Settle
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ),
      )}

      <p className="text-xs text-slate-400">
        Suggested payments fully settle the group in as few transfers as we can find.
      </p>

      {settling && (
        <SettleUpModal group={group} prefill={settling} onClose={() => setSettling(null)} />
      )}
    </div>
  );
}
