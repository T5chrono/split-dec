import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Plus, Users } from "lucide-react";
import { api } from "../lib/api";
import type { Group } from "../lib/types";
import Modal from "../components/Modal";

export default function GroupsPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const { data: groups, isLoading, error } = useQuery({
    queryKey: ["groups"],
    queryFn: () => api.get<Group[]>("/groups"),
  });

  const createGroup = useMutation({
    mutationFn: (groupName: string) => api.post<Group>("/groups", { name: groupName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      setCreating(false);
      setName("");
    },
  });

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Your groups</h1>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> New group
        </button>
      </div>

      {isLoading && <p className="text-slate-500">Loading groups…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}

      {groups && groups.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          <Users className="mx-auto mb-3 h-8 w-8 text-slate-400" />
          No groups yet. Create one to start splitting expenses — a 1-on-1 is just a
          2-person group.
        </div>
      )}

      <ul className="space-y-2">
        {groups?.map((g) => (
          <li key={g.id}>
            <Link
              to={`/groups/${g.id}`}
              className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm hover:border-teal-400"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-600">
                  <Users className="h-5 w-5" />
                </div>
                <div>
                  <div className="font-medium">{g.name}</div>
                  <div className="text-xs text-slate-500">
                    Created {new Date(g.created_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-slate-400" />
            </Link>
          </li>
        ))}
      </ul>

      {creating && (
        <Modal title="New group" onClose={() => setCreating(false)}>
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
              placeholder="Trip to Zakopane"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-500"
            />
            {createGroup.error && (
              <p className="text-sm text-red-600">{(createGroup.error as Error).message}</p>
            )}
            <button
              type="submit"
              disabled={createGroup.isPending || !name.trim()}
              className="w-full rounded-lg bg-teal-600 py-2 font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              {createGroup.isPending ? "Creating…" : "Create group"}
            </button>
          </form>
        </Modal>
      )}
    </div>
  );
}
