import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, HandCoins, Scale } from "lucide-react";
import { api } from "../lib/api";
import type { Balances, GroupDetail, SettlementPayload } from "../lib/types";
import { formatMoney } from "../lib/currency";
import { useI18n } from "../lib/i18n";
import Avatar from "./Avatar";
import SettleUpModal from "./SettleUpModal";
import Spinner from "./Spinner";

export default function BalancesTab({ group }: { group: GroupDetail }) {
  const { t } = useI18n();
  const [settling, setSettling] = useState<SettlementPayload | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? t("formerMember");

  const { data, isLoading, error } = useQuery({
    queryKey: ["balances", group.id],
    queryFn: () => api.get<Balances>(`/groups/${group.id}/balances`),
  });

  const entries = Object.entries(data ?? {});
  const allSettled = entries.every(([, transfers]) => transfers.length === 0);

  return (
    <div className="space-y-5">
      {isLoading && <Spinner label={t("computingBalances")} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}

      {data && allSettled && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          <Scale className="mx-auto mb-3 h-8 w-8 text-slate-400 dark:text-slate-500" />
          {t("allSettled")}
        </div>
      )}

      {entries.map(([currency, transfers]) =>
        transfers.length === 0 ? null : (
          <div key={currency}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
              {currency}
            </h3>
            <ul className="space-y-2">
              {transfers.map((tr, i) => {
                const from = membersById.get(tr.from_user_id);
                const to = membersById.get(tr.to_user_id);
                return (
                  <li
                    key={`${currency}-${i}`}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div className="flex items-center gap-2 text-sm">
                      {from && <Avatar user={from} size={6} />}
                      <span className="font-medium">{nameOf(tr.from_user_id)}</span>
                      <ArrowRight className="h-4 w-4 text-slate-400" />
                      {to && <Avatar user={to} size={6} />}
                      <span className="font-medium">{nameOf(tr.to_user_id)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-red-600 dark:text-red-400">
                        {formatMoney(tr.amount, currency)}
                      </span>
                      <button
                        onClick={() =>
                          setSettling({
                            paid_by_user_id: tr.from_user_id,
                            paid_to_user_id: tr.to_user_id,
                            amount: tr.amount,
                            currency,
                          })
                        }
                        className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700"
                      >
                        <HandCoins className="h-4 w-4" /> {t("settle")}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ),
      )}

      <p className="text-xs text-slate-400 dark:text-slate-500">{t("balancesNote")}</p>

      {settling && (
        <SettleUpModal group={group} prefill={settling} onClose={() => setSettling(null)} />
      )}
    </div>
  );
}
