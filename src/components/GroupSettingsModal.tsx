import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Group, GroupDetail } from "../lib/types";
import { useI18n } from "../lib/i18n";
import Modal from "./Modal";
import ConfirmDialog from "./ConfirmDialog";

export default function GroupSettingsModal({
  group,
  onClose,
}: {
  group: GroupDetail;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [name, setName] = useState(group.name);
  const [deleting, setDeleting] = useState(false);

  const rename = useMutation({
    mutationFn: (newName: string) => api.patch<Group>(`/groups/${group.id}`, { name: newName }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group", group.id] });
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      onClose();
    },
  });

  const deleteGroup = useMutation({
    mutationFn: () => api.delete<void>(`/groups/${group.id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      navigate("/");
    },
  });

  const trimmed = name.trim();

  return (
    <>
      <Modal title={t("groupSettings")} onClose={onClose} dismissOnBackdrop={false}>
        <div className="space-y-5">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (trimmed) rename.mutate(trimmed);
            }}
          >
            <label htmlFor="group-name" className="mb-1 block text-sm font-medium">
              {t("groupName")}
            </label>
            <div className="flex gap-2">
              <input
                id="group-name"
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("groupNamePlaceholder")}
                className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800"
              />
              <button
                type="submit"
                disabled={rename.isPending || !trimmed || trimmed === group.name}
                className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
              >
                {rename.isPending ? t("saving") : t("save")}
              </button>
            </div>
            {rename.error && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {(rename.error as Error).message}
              </p>
            )}
          </form>

          <div className="rounded-xl border border-red-200 p-4 dark:border-red-900">
            <div className="mb-1 text-sm font-semibold text-red-600 dark:text-red-400">
              {t("dangerZone")}
            </div>
            <p className="mb-3 text-sm text-slate-500 dark:text-slate-400">
              {t("deleteGroupHint")}
            </p>
            <button
              type="button"
              onClick={() => setDeleting(true)}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
            >
              <Trash2 className="h-4 w-4" /> {t("deleteGroup")}
            </button>
            {deleteGroup.error && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                {(deleteGroup.error as Error).message}
              </p>
            )}
          </div>
        </div>
      </Modal>

      {/* Rendered after the modal so it stacks above it (both are z-50). */}
      {deleting && (
        <ConfirmDialog
          title={t("deleteGroupTitle")}
          message={`${group.name} — ${t("deleteGroupMsg")}`}
          confirmLabel={t("deleteGroup")}
          busy={deleteGroup.isPending}
          onConfirm={() => deleteGroup.mutate()}
          onCancel={() => setDeleting(false)}
        />
      )}
    </>
  );
}
