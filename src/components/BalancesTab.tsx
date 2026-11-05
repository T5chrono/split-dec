import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, HandCoins, Scale } from "lucide-react";
import type { GroupDetail, SettlementPayload } from "../lib/types";
import { balancesQuery } from "../lib/queries";
import { formatMoney } from "../lib/currency";
import { useI18n } from "../lib/i18n";
import { useAuth } from "../hooks/useAuth";
import Avatar from "./Avatar";
import SettleUpModal from "./SettleUpModal";
import Spinner from "./Spinner";
import EmptyState from "./EmptyState";

export default function BalancesTab({ group }: { group: GroupDetail }) {
  const { t } = useI18n();
  const { session } = useAuth();
  const myId = session?.user.id;
  const [settling, setSettling] = useState<SettlementPayload | null>(null);

  const membersById = new Map(group.members.map((m) => [m.id, m]));
  const nameOf = (id: string) =>
    membersById.get(id)?.full_name ?? membersById.get(id)?.email ?? t("formerMember");

  const { data, isLoading, error } = useQuery(balancesQuery(group.id));

  const entries = Object.entries(data ?? {});
  const allSettled = entries.every(([, transfers]) => transfers.length === 0);

  return (
    <div className="space-y-5">
      {isLoading && <Spinner label={t("computingBalances")} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}

      {data && allSettled && <EmptyState icon={Scale} message={t("allSettled")} />}

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
                // Color from MY perspective: red = money leaving my pocket,
                // green = money coming to me, neutral = between others.
                const iOwe = tr.from_user_id === myId;
                const owedToMe = tr.to_user_id === myId;
                const amountCls = iOwe
                  ? "text-red-600 dark:text-red-400"
                  : owedToMe
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-slate-600 dark:text-slate-300";
                return (
                  // Two lines on a phone — who → whom, then amount and Settle —
                  // because one line leaves the names ~100px at 360px wide and
                  // they wrap into a column. One line again from `sm` up.
                  <li
                    key={`${currency}-${i}`}
                    className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between dark:border-slate-700 dark:bg-slate-900"
                  >
                    <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                      <span className="flex min-w-0 items-center gap-2">
                        {from && <Avatar user={from} size={6} />}
                        <span className="font-medium">
                          {iOwe ? t("you") : nameOf(tr.from_user_id)}
                        </span>
                      </span>
                      <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
                      <span className="flex min-w-0 items-center gap-2">
                        {to && <Avatar user={to} size={6} />}
                        <span className="font-medium">
                          {owedToMe ? t("you") : nameOf(tr.to_user_id)}
                        </span>
                      </span>
                    </div>
                    <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
                      <div className="sm:text-right">
                        <div className={`whitespace-nowrap font-semibold ${amountCls}`}>
                          {formatMoney(tr.amount, currency)}
                        </div>
                        {(iOwe || owedToMe) && (
                          <div className={`whitespace-nowrap text-[10px] leading-tight ${amountCls}`}>
                            {iOwe ? t("youOwe") : t("owedToYou")}
                          </div>
                        )}
                      </div>
                      <button
                        onClick={() =>
                          setSettling({
                            paid_by_user_id: tr.from_user_id,
                            paid_to_user_id: tr.to_user_id,
                            amount: tr.amount,
                            currency,
                          })
                        }
                        className="flex shrink-0 items-center gap-1 whitespace-nowrap rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700"
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
