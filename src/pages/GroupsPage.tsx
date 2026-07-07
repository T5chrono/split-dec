import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronRight, MailOpen, Plus, Users, X } from "lucide-react";
import { api } from "../lib/api";
import type { Group } from "../lib/types";
import {
  expensesQuery,
  groupDetailQuery,
  groupsQuery,
  myInvitationsQuery,
} from "../lib/queries";
import { useI18n } from "../lib/i18n";
import Modal from "../components/Modal";
import ListSkeleton from "../components/ListSkeleton";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const { t, dateLocale } = useI18n();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const { data: groups, isLoading, error } = useQuery(groupsQuery());

  // Warm a group's data the moment the user shows intent to open it.
  const prefetchGroup = (id: string) => {
    queryClient.prefetchQuery(groupDetailQuery(id));
    queryClient.prefetchQuery(expensesQuery(id, 0));
  };

  const createGroup = useMutation({
    mutationFn: (groupName: string) => api.post<Group>("/groups", { name: groupName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      setCreating(false);
      setName("");
    },
  });

  const { data: myInvitations } = useQuery(myInvitationsQuery());

  const respond = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "accept" | "decline" }) =>
      api.post<void>(`/invitations/${id}/${action}`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-invitations"] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t("yourGroups")}</h1>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> {t("newGroup")}
        </button>
      </div>

      {myInvitations && myInvitations.length > 0 && (
        <div className="mb-5 space-y-2">
          {myInvitations.map((inv) => (
            <div
              key={inv.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 dark:border-teal-900 dark:bg-teal-950/40"
            >
              <div className="flex min-w-0 items-center gap-3">
                <MailOpen className="h-5 w-5 shrink-0 text-teal-600 dark:text-teal-400" />
                <p className="min-w-0 truncate text-sm text-slate-700 dark:text-slate-200">
                  <span className="font-medium">{inv.invited_by_name ?? "?"}</span>{" "}
                  {t("invitedYouTo")} <span className="font-medium">{inv.group_name}</span>
                </p>
              </div>
              <div className="flex shrink-0 gap-1.5">
                <button
                  onClick={() => respond.mutate({ id: inv.id, action: "accept" })}
                  disabled={respond.isPending}
                  className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-teal-700 disabled:opacity-50"
                >
                  <Check className="h-3.5 w-3.5" /> {t("accept")}
                </button>
                <button
                  onClick={() => respond.mutate({ id: inv.id, action: "decline" })}
                  disabled={respond.isPending}
                  className="flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
                >
                  <X className="h-3.5 w-3.5" /> {t("decline")}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {isLoading && <ListSkeleton rows={3} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}

      {groups && groups.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
          <Users className="mx-auto mb-3 h-8 w-8 text-slate-400 dark:text-slate-500" />
          {t("noGroups")}
        </div>
      )}

      <ul className="space-y-2">
        {groups?.map((g) => (
          <li key={g.id}>
            <Link
              to={`/groups/${g.id}`}
              onMouseEnter={() => prefetchGroup(g.id)}
              onTouchStart={() => prefetchGroup(g.id)}
              onFocus={() => prefetchGroup(g.id)}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:border-teal-400 dark:border-slate-700 dark:bg-slate-900 dark:hover:border-teal-500"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-600 dark:bg-teal-950 dark:text-teal-400">
                  <Users className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-medium">{g.name}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-400">
                    {t("createdOn")} {new Date(g.created_at).toLocaleDateString(dateLocale)}
                  </div>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-slate-400" />
            </Link>
          </li>
        ))}
      </ul>

      {creating && (
        <Modal title={t("newGroup")} onClose={() => setCreating(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) createGroup.mutate(name.trim());
            }}
            className="space-y-4"
          >
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("groupNamePlaceholder")}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800"
            />
            {createGroup.error && (
              <p className="text-sm text-red-600 dark:text-red-400">
                {(createGroup.error as Error).message}
              </p>
            )}
            <button
              type="submit"
              disabled={createGroup.isPending || !name.trim()}
              className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {createGroup.isPending ? t("creating") : t("createGroup")}
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
