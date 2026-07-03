import { useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { parseLocalISO, toLocalISO, todayLocalISO } from "../lib/dates";
import { useI18n } from "../lib/i18n";

const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export default function DatePicker({
  value,
  onChange,
}: {
  value: string; // YYYY-MM-DD
  onChange: (v: string) => void;
}) {
  const { t, dateLocale, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const selected = parseLocalISO(value);
  const [view, setView] = useState({ y: selected.getFullYear(), m: selected.getMonth() });
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const weekStart = lang === "pl" ? 1 : 0; // Monday-first in Polish
  const monthFmt = new Intl.DateTimeFormat(dateLocale, { month: "long", year: "numeric" });
  const weekdayFmt = new Intl.DateTimeFormat(dateLocale, { weekday: "short" });
  const triggerFmt = new Intl.DateTimeFormat(dateLocale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  // 2023-01-01 was a Sunday; walk forward to label the weekday header row.
  const weekdays = Array.from({ length: 7 }, (_, i) =>
    weekdayFmt.format(new Date(2023, 0, 1 + weekStart + i)).replace(".", ""),
  );

  const firstOfMonth = new Date(view.y, view.m, 1);
  const startOffset = (firstOfMonth.getDay() - weekStart + 7) % 7;
  const cells = Array.from(
    { length: 42 },
    (_, i) => new Date(view.y, view.m, 1 - startOffset + i),
  );
  const today = todayLocalISO();

  const shiftMonth = (delta: number) => {
    const d = new Date(view.y, view.m + delta, 1);
    setView({ y: d.getFullYear(), m: d.getMonth() });
  };

  const select = (d: Date) => {
    onChange(toLocalISO(d));
    setOpen(false);
  };

  const openPicker = () => {
    setView({ y: selected.getFullYear(), m: selected.getMonth() });
    setOpen(!open);
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={openPicker}
        className="flex w-full items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800"
      >
        <CalendarDays className="h-4 w-4 shrink-0 text-slate-400 dark:text-slate-500" />
        <span>{capitalize(triggerFmt.format(selected))}</span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-20 mt-2 w-72 rounded-xl border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() => shiftMonth(-1)}
              title={t("prevMonth")}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="text-sm font-semibold">
              {capitalize(monthFmt.format(firstOfMonth))}
            </span>
            <button
              type="button"
              onClick={() => shiftMonth(1)}
              title={t("nextMonth")}
              className="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 text-center">
            {weekdays.map((w) => (
              <div
                key={w}
                className="pb-1 text-[11px] font-medium uppercase text-slate-400 dark:text-slate-500"
              >
                {w}
              </div>
            ))}
            {cells.map((d) => {
              const iso = toLocalISO(d);
              const inMonth = d.getMonth() === view.m;
              const isSelected = iso === value;
              const isToday = iso === today;
              return (
                <button
                  key={iso}
                  type="button"
                  onClick={() => select(d)}
                  className={[
                    "mx-auto flex h-9 w-9 items-center justify-center rounded-full text-sm transition",
                    isSelected
                      ? "bg-teal-600 font-semibold text-white"
                      : isToday
                        ? "font-semibold text-teal-600 ring-1 ring-inset ring-teal-500 hover:bg-teal-50 dark:text-teal-400 dark:hover:bg-slate-800"
                        : inMonth
                          ? "text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800"
                          : "text-slate-300 hover:bg-slate-50 dark:text-slate-600 dark:hover:bg-slate-800/50",
                  ].join(" ")}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>

          <div className="mt-2 border-t border-slate-100 pt-2 text-center dark:border-slate-800">
            <button
              type="button"
              onClick={() => select(new Date())}
              className="rounded-md px-3 py-1 text-sm font-medium text-teal-600 hover:bg-teal-50 dark:text-teal-400 dark:hover:bg-slate-800"
            >
              {t("today")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
