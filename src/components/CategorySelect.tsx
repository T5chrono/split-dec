import { useEffect, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";
import { CATEGORY_GROUPS, CategoryIcon } from "../lib/categories";
import { useI18n } from "../lib/i18n";

/** Grouped category option list, shared by the form field picker and the
 *  expense-row icon popover. The list renders from the top (General first)
 *  so the user always starts at the top and scrolls down. */
export function CategoryOptions({
  value,
  onSelect,
}: {
  value: string;
  onSelect: (v: string) => void;
}) {
  const { tCategory, tCategoryGroup } = useI18n();
  return (
    <>
      {CATEGORY_GROUPS.map((g) => (
        <div key={g.group}>
          <div className="px-3 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
            {tCategoryGroup(g.group)}
          </div>
          {g.categories.map((c) => {
            const selected = c.value === value;
            return (
              <button
                key={c.value}
                type="button"
                data-value={c.value}
                role="option"
                aria-selected={selected}
                onClick={() => onSelect(c.value)}
                className={[
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left text-sm outline-none",
                  selected
                    ? "bg-teal-50 font-medium text-teal-700 dark:bg-teal-950 dark:text-teal-300"
                    : "text-slate-700 hover:bg-slate-50 focus-visible:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800 dark:focus-visible:bg-slate-800",
                ].join(" ")}
              >
                <c.icon className="h-5 w-5 shrink-0 text-slate-500 dark:text-slate-400" />
                {tCategory(c.value)}
              </button>
            );
          })}
        </div>
      ))}
    </>
  );
}

export default function CategorySelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const { t, tCategory } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  // Always open at the top of the list; focus the first option for keyboard use.
  useEffect(() => {
    if (!open) return;
    const list = listRef.current;
    if (!list) return;
    list.scrollTop = 0;
    list.querySelector<HTMLButtonElement>("[data-value]")?.focus();
  }, [open]);

  const select = (v: string) => {
    onChange(v);
    setOpen(false);
    triggerRef.current?.focus();
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      setOpen(false);
      triggerRef.current?.focus();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const options = Array.from(
      listRef.current?.querySelectorAll<HTMLButtonElement>("[data-value]") ?? [],
    );
    const idx = options.findIndex((o) => o === document.activeElement);
    const next = options[idx + (e.key === "ArrowDown" ? 1 : -1)];
    next?.focus();
  };

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        ref={triggerRef}
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t("category")}
        className="flex w-full items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 py-2 text-left outline-none focus:border-teal-500 dark:border-slate-600 dark:bg-slate-800"
      >
        <CategoryIcon
          category={value}
          className="h-5 w-5 shrink-0 text-slate-500 dark:text-slate-400"
        />
        <span className="min-w-0 flex-1 truncate">{tCategory(value)}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
      </button>

      {open && (
        <div
          role="listbox"
          ref={listRef}
          onKeyDown={onKeyDown}
          className="absolute left-0 top-full z-20 mt-2 max-h-72 w-full min-w-56 overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-700 dark:bg-slate-900 dark:shadow-black/40"
        >
          <CategoryOptions value={value} onSelect={select} />
        </div>
      )}
    </div>
  );
}
