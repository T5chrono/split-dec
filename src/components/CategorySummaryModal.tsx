import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, ClipboardCopy } from "lucide-react";
import { CATEGORY_GROUPS } from "../lib/categories";
import { fromUnits, spreadsheetColumn, summarizeByGroup } from "../lib/categorySummary";
import { formatMoney } from "../lib/currency";
import { categoryTotalsQuery } from "../lib/queries";
import { useI18n } from "../lib/i18n";
import Modal from "./Modal";
import ListSkeleton from "./ListSkeleton";

/** One month of a group's spending folded into the twelve top-level category
 *  groups, with a button that copies the amounts as a single spreadsheet
 *  column. Always all twelve rows in `CATEGORY_GROUPS` order, zeros included,
 *  so the column pasted one month lines up with the one pasted the next. */
export default function CategorySummaryModal({
  groupId,
  month,
  monthLabel,
  onClose,
}: {
  groupId: string;
  /** "YYYY-MM" */
  month: string;
  monthLabel: string;
  onClose: () => void;
}) {
  const { t, tCategoryGroup, lang } = useI18n();
  const { data, isLoading, error } = useQuery(categoryTotalsQuery(groupId, month));
  const [picked, setPicked] = useState<string | null>(null);
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");

  // The "Copied" tick is feedback for one click, not a state to stay in.
  useEffect(() => {
    if (copy !== "copied") return;
    const id = setTimeout(() => setCopy("idle"), 2000);
    return () => clearTimeout(id);
  }, [copy]);

  const byCurrency = data ? summarizeByGroup(data) : null;
  const currencies = byCurrency ? [...byCurrency.keys()] : [];
  const currency = picked && currencies.includes(picked) ? picked : (currencies[0] ?? null);
  const sums = currency ? byCurrency!.get(currency)! : null;
  const total = sums?.reduce((a, b) => a + b, 0n) ?? 0n;

  const copyColumn = async () => {
    if (!sums || !currency) return;
    try {
      await navigator.clipboard.writeText(spreadsheetColumn(sums, currency, lang));
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  };

  return (
    <Modal title={t("monthSummaryTitle", { month: monthLabel })} onClose={onClose}>
      {isLoading && <ListSkeleton rows={4} />}
      {error && <p className="text-red-600 dark:text-red-400">{(error as Error).message}</p>}
      {data && !currency && (
        <p className="text-sm text-slate-500 dark:text-slate-400">{t("noExpensesInMonth")}</p>
      )}

      {currency && sums && (
        <>
          {currencies.length > 1 && (
            <div role="group" className="mb-3 flex flex-wrap gap-1">
              {currencies.map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    setPicked(c);
                    setCopy("idle");
                  }}
                  aria-pressed={c === currency}
                  className={`rounded-lg border px-3 py-1 text-sm ${
                    c === currency
                      ? "border-teal-500 bg-teal-50 font-medium text-teal-700 dark:bg-teal-950 dark:text-teal-300"
                      : "border-slate-300 bg-white text-slate-600 hover:border-teal-400 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          <table className="w-full text-sm">
            <tbody>
              {CATEGORY_GROUPS.map((g, i) => (
                <tr
                  key={g.group}
                  className={`border-b border-slate-100 dark:border-slate-800 ${
                    sums[i] === 0n ? "text-slate-400 dark:text-slate-500" : ""
                  }`}
                >
                  <td className="py-1.5 pr-3">{tCategoryGroup(g.group)}</td>
                  <td className="whitespace-nowrap py-1.5 text-right tabular-nums">
                    {formatMoney(fromUnits(sums[i]), currency)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-semibold">
                <td className="pt-2 pr-3">{t("summaryTotal")}</td>
                <td className="whitespace-nowrap pt-2 text-right tabular-nums">
                  {formatMoney(fromUnits(total), currency)}
                </td>
              </tr>
            </tfoot>
          </table>

          <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{t("summaryEveryone")}</p>

          <div className="mt-4 flex flex-col gap-2">
            <button
              onClick={copyColumn}
              className="flex items-center justify-center gap-2 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700"
            >
              {copy === "copied" ? (
                <>
                  <Check className="h-4 w-4" /> {t("copiedForExcel")}
                </>
              ) : (
                <>
                  <ClipboardCopy className="h-4 w-4" /> {t("copyForExcel")}
                </>
              )}
            </button>
            <p className="text-xs text-slate-500 dark:text-slate-400">{t("summaryCopyHint")}</p>
            {copy === "failed" && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {t("copyFailed")}
              </p>
            )}
          </div>
        </>
      )}
    </Modal>
  );
}
