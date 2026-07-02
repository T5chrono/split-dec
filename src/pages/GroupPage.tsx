import { useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { GroupDetail } from "../lib/types";
import ExpensesTab from "../components/ExpensesTab";
import BalancesTab from "../components/BalancesTab";
import SettlementsTab from "../components/SettlementsTab";
import MembersTab from "../components/MembersTab";

const TABS = ["Expenses", "Balances", "Settlements", "Members"] as const;
type Tab = (typeof TABS)[number];

export default function GroupPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const [tab, setTab] = useState<Tab>("Expenses");

  const { data: group, isLoading, error } = useQuery({
    queryKey: ["group", groupId],
    queryFn: () => api.get<GroupDetail>(`/groups/${groupId}`),
    enabled: !!groupId,
  });

  if (isLoading) return <p className="text-slate-500">Loading group…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!group) return null;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold">{group.name}</h1>
      <p className="mb-4 text-sm text-slate-500">
        {group.members.length} member{group.members.length === 1 ? "" : "s"}
      </p>

      <div className="mb-5 flex gap-1 rounded-lg bg-slate-200/60 p-1">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition ${
              tab === t ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Expenses" && <ExpensesTab group={group} />}
      {tab === "Balances" && <BalancesTab group={group} />}
      {tab === "Settlements" && <SettlementsTab group={group} />}
      {tab === "Members" && <MembersTab group={group} />}
    </div>
  );
}
