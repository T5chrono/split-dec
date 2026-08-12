import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { useI18n } from "../lib/i18n";

/** Rendered inside Layout for any unmatched signed-in route. Replaces a silent
 *  redirect to "/", which made a mistyped or stale link look like it had
 *  worked and quietly dropped you on the groups list. */
export default function NotFoundPage() {
  const { t } = useI18n();

  return (
    <div className="py-16 text-center">
      <Compass className="mx-auto mb-4 h-12 w-12 text-slate-300 dark:text-slate-600" />
      <h1 className="text-2xl font-bold">{t("notFoundTitle")}</h1>
      <p className="mx-auto mt-3 max-w-md text-slate-500 dark:text-slate-400">
        {t("notFoundBody")}
      </p>
      <Link
        to="/"
        className="mt-6 inline-flex items-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
      >
        {t("backToGroups")}
      </Link>
    </div>
  );
}
