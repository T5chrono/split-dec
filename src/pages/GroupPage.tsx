import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { GroupDetail } from "../lib/types";
import { useI18n, type TKey } from "../lib/i18n";
import ExpensesTab from "../components/ExpensesTab";
import BalancesTab from "../components/BalancesTab";
import SettlementsTab from "../components/SettlementsTab";
import MembersTab from "../components/MembersTab";
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

  const { data: group, isLoading, error } = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => api.get<GroupDetail>(`/groups/${groupId}`),
    enabled: !!groupId,
  });

  if (isLoading) return <Spinner label={t("loading")} />;
  if (error) return <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>;
  if (!group) return null;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">{group.name}</h1>
      <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">
        {membersLabel(group.members.length)}
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
    </div>
  );
}
