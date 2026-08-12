import { Plus, type LucideIcon } from "lucide-react";

/** The "nothing here yet" card, shared by the groups list and the three group
 *  tabs — the same ten classes were repeated at each one. Where there is an
 *  obvious next step, pass `action`: an empty list that explains itself and
 *  offers the button is worth more than one that only explains itself. */
export default function EmptyState({
  icon: Icon,
  message,
  action,
}: {
  icon?: LucideIcon;
  message: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">
      {Icon && <Icon className="mx-auto mb-3 h-8 w-8 text-slate-400 dark:text-slate-500" />}
      <p className="mx-auto max-w-sm">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mx-auto mt-5 flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
        >
          <Plus className="h-4 w-4" /> {action.label}
        </button>
      )}
    </div>
  );
}
