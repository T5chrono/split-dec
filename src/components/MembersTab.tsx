import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, UserMinus, UserPlus } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { GroupDetail, User } from "../lib/types";
import Avatar from "./Avatar";

type FoundUser = Pick<User, "id" | "full_name" | "avatar_url">;

export default function MembersTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [found, setFound] = useState<FoundUser | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["group", group.id] });

  const search = useMutation({
    mutationFn: (q: string) =>
      api.get<FoundUser>(`/users/search?email=${encodeURIComponent(q)}`),
    onSuccess: (user) => {
      setFound(user);
      setSearchError(null);
    },
    onError: (e) => {
      setFound(null);
      setSearchError(e instanceof ApiError ? e.message : "Search failed");
    },
  });

  const addMember = useMutation({
    mutationFn: (userId: string) =>
      api.post<User>(`/groups/${group.id}/members`, { user_id: userId }),
    onSuccess: () => {
      setFound(null);
      setEmail("");
      invalidate();
    },
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      api.delete<void>(`/groups/${group.id}/members/${userId}`),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (email.trim()) search.mutate(email.trim());
        }}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
      >
        <label className="mb-2 block text-sm font-medium">Invite by email</label>
        <div className="flex gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="friend@example.com"
            className="flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-500"
          />
          <button
            type="submit"
            disabled={search.isPending}
            className="flex items-center gap-2 rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            <Search className="h-4 w-4" /> Find
          </button>
        </div>
        {searchError && <p className="mt-2 text-sm text-red-600">{searchError}</p>}
        {found && (
          <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
            <div className="flex items-center gap-2">
              <Avatar user={{ ...found, email: "" }} size={8} />
              <span className="text-sm font-medium">{found.full_name ?? "Unnamed user"}</span>
            </div>
            <button
              onClick={() => addMember.mutate(found.id)}
              disabled={addMember.isPending}
              className="flex items-center gap-1 rounded-lg bg-teal-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            >
              <UserPlus className="h-4 w-4" /> Add
            </button>
          </div>
        )}
        {addMember.error && (
          <p className="mt-2 text-sm text-red-600">{(addMember.error as Error).message}</p>
        )}
      </form>

      <ul className="space-y-2">
        {group.members.map((m) => (
          <li
            key={m.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
          >
            <div className="flex items-center gap-3">
              <Avatar user={m} size={10} />
              <div>
                <div className="font-medium">{m.full_name ?? m.email}</div>
                <div className="text-xs text-slate-500">{m.email}</div>
              </div>
            </div>
            <button
              onClick={() => removeMember.mutate(m.id)}
              disabled={removeMember.isPending}
              title="Remove from group (must be fully settled)"
              className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"
            >
              <UserMinus className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
      {removeMember.error && (
        <p className="text-sm text-red-600">{(removeMember.error as Error).message}</p>
      )}
    </div>
  );
}
