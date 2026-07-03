import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { LogOut, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../hooks/useAuth";
import { useI18n } from "../lib/i18n";
import Modal from "./Modal";
import ConfirmDialog from "./ConfirmDialog";

export default function AccountModal({ onClose }: { onClose: () => void }) {
  const { session, signOut } = useAuth();
  const { t } = useI18n();
  const [confirming, setConfirming] = useState(false);

  const meta = session?.user.user_metadata as
    | { full_name?: string; name?: string; avatar_url?: string; picture?: string }
    | undefined;
  const displayName = meta?.full_name ?? meta?.name ?? "";
  const email = session?.user.email ?? "";
  const avatar = meta?.avatar_url ?? meta?.picture;

  const deleteAccount = useMutation({
    mutationFn: () => api.delete<void>("/users/me"),
    onSuccess: async () => {
      await signOut();
    },
  });

  return (
    <>
      <Modal title={t("account")} onClose={onClose}>
        <div className="space-y-5">
          <div className="flex items-center gap-3">
            {avatar && (
              <img
                src={avatar}
                alt=""
                referrerPolicy="no-referrer"
                className="h-12 w-12 rounded-full"
              />
            )}
            <div>
              <div className="font-medium">{displayName}</div>
              <div className="text-sm text-slate-500 dark:text-slate-400">
                {t("signedInAs")} {email}
              </div>
            </div>
          </div>

          <button
            onClick={signOut}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-300 py-2 text-sm font-medium hover:bg-slate-50 dark:border-slate-600 dark:hover:bg-slate-800"
          >
            <LogOut className="h-4 w-4" /> {t("signOut")}
          </button>

          <div className="rounded-lg border border-red-200 p-3 dark:border-red-900">
            <div className="mb-2 text-sm font-semibold text-red-600 dark:text-red-400">
              {t("dangerZone")}
            </div>
            <button
              onClick={() => setConfirming(true)}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              <Trash2 className="h-4 w-4" /> {t("deleteAccount")}
            </button>
            {deleteAccount.error && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {(deleteAccount.error as Error).message}
              </p>
            )}
          </div>
        </div>
      </Modal>

      {confirming && (
        <ConfirmDialog
          title={t("deleteAccountTitle")}
          message={t("deleteAccountWarning")}
          confirmLabel={
            deleteAccount.isPending ? t("deletingAccount") : t("deleteAccountConfirm")
          }
          busy={deleteAccount.isPending}
          onConfirm={() => deleteAccount.mutate()}
          onCancel={() => setConfirming(false)}
        />
      )}
    </>
  );
}
