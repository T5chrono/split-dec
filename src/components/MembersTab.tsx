import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, MailPlus, UserMinus, X } from "lucide-react";
import { api } from "../lib/api";
import type { GroupDetail, Invitation, InvitationCreated, User } from "../lib/types";
import { useI18n } from "../lib/i18n";
import Avatar from "./Avatar";
import ConfirmDialog from "./ConfirmDialog";

const inputCls =
  "flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800";

export default function MembersTab({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [result, setResult] = useState<InvitationCreated | null>(null);
  const [removing, setRemoving] = useState<User | null>(null);

  const { data: invitations } = useQuery({
    queryKey: ["invitations", group.id],
    queryFn: () => api.get<Invitation[]>(`/groups/${group.id}/invitations`),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["group", group.id] });
    queryClient.invalidateQueries({ queryKey: ["invitations", group.id] });
  };

  const invite = useMutation({
    mutationFn: (address: string) =>
      api.post<InvitationCreated>(`/groups/${group.id}/invitations`, { email: address }),
    onSuccess: (created) => {
      setResult(created);
      setEmail("");
      invalidate();
    },
  });

  const cancelInvitation = useMutation({
    mutationFn: (id: string) => api.delete<void>(`/invitations/${id}`),
    onSuccess: invalidate,
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      api.delete<void>(`/groups/${group.id}/members/${userId}`),
    onSuccess: () => {
      setRemoving(null);
      invalidate();
    },
  });

  const mailtoHref = (address: string) =>
    `mailto:${address}?subject=${encodeURIComponent(t("inviteEmailSubject"))}&body=${encodeURIComponent(
      t("inviteEmailBody").replace("{group}", group.name) + "\n\nhttps://split-dec.vercel.app",
    )}`;

  return (
    <div className="space-y-5">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setResult(null);
          if (email.trim()) invite.mutate(email.trim());
        }}
        className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900"
      >
        <label className="mb-2 block text-sm font-medium">{t("inviteByEmail")}</label>
        <div className="flex gap-2">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="friend@example.com"
            className={inputCls}
          />
          <button
            type="submit"
            disabled={invite.isPending}
            className="flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
          >
            <MailPlus className="h-4 w-4" /> {t("invite")}
          </button>
        </div>
        {invite.error && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
            {(invite.error as Error).message}
          </p>
        )}
        {result && (
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-800">
            {result.user_exists ? (
              <p className="text-emerald-700 dark:text-emerald-400">{t("invitationSentInApp")}</p>
            ) : result.email_sent ? (
              <p className="text-emerald-700 dark:text-emerald-400">{t("invitationEmailSent")}</p>
            ) : (
              <div className="space-y-2">
                <p className="text-slate-600 dark:text-slate-300">{t("inviteeNotOnSplitDec")}</p>
                <a
                  href={mailtoHref(result.email)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-700 dark:bg-slate-700 dark:hover:bg-slate-600"
                >
                  <Mail className="h-3.5 w-3.5" /> {t("openEmailDraft")}
                </a>
              </div>
            )}
          </div>
        )}
      </form>

      {invitations && invitations.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            {t("pendingInvitations")}
          </h3>
          <ul className="space-y-2">
            {invitations.map((inv) => (
              <li
                key={inv.id}
                className="flex items-center justify-between rounded-xl border border-dashed border-slate-300 bg-white px-4 py-2.5 dark:border-slate-600 dark:bg-slate-900"
              >
                <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                  <Mail className="h-4 w-4 text-slate-400" />
                  {inv.email}
                </div>
                <button
                  onClick={() => cancelInvitation.mutate(inv.id)}
                  title={t("cancelInvitation")}
                  className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
                >
                  <X className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ul className="space-y-2">
        {group.members.map((m) => (
          <li
            key={m.id}
            className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900"
          >
            <div className="flex items-center gap-3">
              <Avatar user={m} size={10} />
              <div>
                <div className="font-medium">{m.full_name ?? m.email}</div>
                <div className="text-xs text-slate-500 dark:text-slate-400">{m.email}</div>
              </div>
            </div>
            <button
              onClick={() => setRemoving(m)}
              disabled={removeMember.isPending}
              title={t("removeMemberTip")}
              className="rounded-md p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-950 dark:hover:text-red-400"
            >
              <UserMinus className="h-4 w-4" />
            </button>
          </li>
        ))}
      </ul>
      {removeMember.error && (
        <p className="text-sm text-red-600 dark:text-red-400">
          {(removeMember.error as Error).message}
        </p>
      )}

      {removing && (
        <ConfirmDialog
          title={t("removeMemberTitle")}
          message={`${removing.full_name ?? removing.email} — ${t("removeMemberMsg")}`}
          busy={removeMember.isPending}
          onConfirm={() => removeMember.mutate(removing.id)}
          onCancel={() => setRemoving(null)}
        />
      )}
    </div>
  );
}
