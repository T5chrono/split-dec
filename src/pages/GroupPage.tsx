import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Check, Pencil, X } from "lucide-react";
import { api } from "../lib/api";
import type { Group } from "../lib/types";
import {
  balancesQuery,
  expensesQuery,
  groupDetailQuery,
  groupInvitationsQuery,
  settlementsQuery,
} from "../lib/queries";
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
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");

  const queryClient = useQueryClient();
  const { data: group, isLoading, error } = useQuery({
    ...groupDetailQuery(groupId!),
    enabled: !!groupId,
  });

  // Warm every tab's data in parallel so switching tabs is instant.
  useEffect(() => {
    if (!groupId) return;
    queryClient.prefetchQuery(expensesQuery(groupId, 0));
    queryClient.prefetchQuery(balancesQuery(groupId));
    queryClient.prefetchQuery(settlementsQuery(groupId));
    queryClient.prefetchQuery(groupInvitationsQuery(groupId));
  }, [groupId, queryClient]);

  const rename = useMutation({
    mutationFn: (name: string) => api.patch<Group>(`/groups/${groupId}`, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group", groupId] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      setRenaming(false);
    },
  });

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
      {renaming ? (
        <form
          className="mb-1 flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (newName.trim()) rename.mutate(newName.trim());
          }}
        >
          <input
            autoFocus
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setRenaming(false)}
            className="w-full max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xl font-bold outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800"
          />
          <button
            type="submit"
            disabled={rename.isPending || !newName.trim()}
            title={t("save")}
            className="rounded-md p-2 text-teal-600 hover:bg-teal-50 disabled:opacity-50 dark:hover:bg-slate-800"
          >
            <Check className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => setRenaming(false)}
            title={t("cancel")}
            className="rounded-md p-2 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="h-5 w-5" />
          </button>
        </form>
      ) : (
        <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold">
          {group.name}
          <button
            onClick={() => {
              setNewName(group.name);
              setRenaming(true);
            }}
            title={t("renameGroup")}
            aria-label={t("renameGroup")}
            className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-teal-600 dark:hover:bg-slate-800 dark:hover:text-teal-400"
          >
            <Pencil className="h-4 w-4" />
          </button>
        </h1>
      )}
      {rename.error && (
        <p className="mb-2 text-sm text-red-600 dark:text-red-400">
          {(rename.error as Error).message}
        </p>
      )}
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
