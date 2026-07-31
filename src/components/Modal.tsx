import { X } from "lucide-react";
import type { ReactNode } from "react";
import { useI18n } from "../lib/i18n";

export default function Modal({
  title,
  onClose,
  dismissOnBackdrop = true,
  children,
}: {
  title: string;
  onClose: () => void;
  /** Forms that hold unsaved input pass `false`: a stray click on the
   *  backdrop must not discard what the user typed. Dialogs with an explicit
   *  cancel action (nothing to lose) keep the default. */
  dismissOnBackdrop?: boolean;
  children: ReactNode;
}) {
  const { t } = useI18n();
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-16 dark:bg-black/60"
      onClick={dismissOnBackdrop ? onClose : undefined}
    >
      <div
        className="w-full max-w-lg rounded-xl bg-white p-5 shadow-xl dark:bg-slate-900 dark:shadow-black/40"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            onClick={onClose}
            title={t("close")}
            aria-label={t("close")}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
