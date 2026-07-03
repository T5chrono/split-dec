import { Loader2 } from "lucide-react";

export default function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-slate-500 dark:text-slate-400">
      <Loader2 className="h-6 w-6 animate-spin text-teal-600 dark:text-teal-400" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
