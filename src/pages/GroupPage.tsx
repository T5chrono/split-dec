import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Settings } from "lucide-react";
import {
  balancesQuery,
  expensesQuery,
  groupDetailQuery,
  groupInvitationsQuery,
  settlementsQuery,
  totalsQuery,
} from "../lib/queries";
import { formatMoney } from "../lib/currency";
import { useI18n, type TKey } from "../lib/i18n";
import ExpensesTab from "../components/ExpensesTab";
import BalancesTab from "../components/BalancesTab";
import SettlementsTab from "../components/SettlementsTab";
import MembersTab from "../components/MembersTab";
import GroupSettingsModal from "../components/GroupSettingsModal";
import Spinner from "../components/Spinner";

const TABS: { id: string; label: TKey }[] = [
  { id: "expenses", label: "tabExpenses" },
  { id: "balances", label: "tabBalances" },
  { id: "settlements", label: "tabSettlements" },
  { id: "members", label: "tabMembers" },
];

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const { t, membersLabel } = useI18n();
  const [tab, setTab] = useState("expenses");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const queryClient = useQueryClient();
  const { data: group, isLoading, error } = useQuery({
    ...groupDetailQuery(groupId!),
    enabled: !!groupId,
  });

  const { data: totals } = useQuery({ ...totalsQuery(groupId!), enabled: !!groupId });

  // Warm every tab's data in parallel so switching tabs is instant.
  useEffect(() => {
    if (!groupId) return;
    queryClient.prefetchQuery(expensesQuery(groupId, 0));
    queryClient.prefetchQuery(balancesQuery(groupId));
    queryClient.prefetchQuery(settlementsQuery(groupId));
    queryClient.prefetchQuery(groupInvitationsQuery(groupId));
  }, [groupId, queryClient]);

  if (isLoading) return <Spinner label={t("loading")} />;
  if (error) return <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>;
  if (!group) return null;

  return (
    <div>
      <Link
        to="/"
        className="mb-3 inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400"
      >
        <ArrowLeft className="h-4 w-4" /> {t("yourGroups")}
      </Link>
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold">
        {group.name}
        <button
          onClick={() => setSettingsOpen(true)}
          title={t("groupSettings")}
          aria-label={t("groupSettings")}
          className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-teal-600 dark:hover:bg-slate-800 dark:hover:text-teal-400"
        >
          <Settings className="h-4 w-4" />
        </button>
      </h1>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        {membersLabel(group.members.length)}
        {totals && totals.length > 0 && (
          <>
            {" · "}
            {t("totalSpent")}:{" "}
            {/* One entry per currency, joined — never summed (no exchange rates). */}
            <span className="font-semibold text-slate-700 dark:text-slate-200">
              {totals.map((tt) => formatMoney(tt.total, tt.currency)).join(" · ")}
            </span>
          </>
        )}
      </p>

      <div className="mb-5 flex gap-1 rounded-lg bg-slate-200/60 p-1 dark:bg-slate-800">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
              tab === id
                ? "bg-white text-slate-900 shadow-sm dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200"
            }`}
          >
            {t(label)}
          </button>
        ))}
      </div>

      {tab === "expenses" && <ExpensesTab group={group} />}
      {tab === "balances" && <BalancesTab group={group} />}
      {tab === "settlements" && <SettlementsTab group={group} />}
      {tab === "members" && <MembersTab group={group} />}

      {settingsOpen && (
        <GroupSettingsModal group={group} onClose={() => setSettingsOpen(false)} />
      )}
    </div>
  );
}
