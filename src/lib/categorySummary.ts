import { CATEGORY_GROUPS } from "./categories";
import { precisionFor } from "./currency";
import type { CategoryTotal } from "./types";

/** Money in the backend's own unit — ten-thousandths, the scale of
 *  NUMERIC(14,4) — as a BigInt, so adding up a month never touches a float. */
const SCALE = 4;

function toUnits(amount: string): bigint {
  const [intPart, frac = ""] = amount.split(".");
  return BigInt(intPart) * 10n ** BigInt(SCALE) + BigInt(frac.padEnd(SCALE, "0").slice(0, SCALE) || "0");
}

/** Back to a backend-shaped string ("120.5000"), which `formatMoney` takes. */
export function fromUnits(units: bigint): string {
  const s = units.toString().padStart(SCALE + 1, "0");
  return `${s.slice(0, -SCALE)}.${s.slice(-SCALE)}`;
}

const GROUP_INDEX: ReadonlyMap<string, number> = new Map(
  CATEGORY_GROUPS.flatMap((g, i) => g.categories.map((c) => [c.value, i] as const)),
);
// A value missing from the table (a category the backend gained before this
// bundle did) lands under the last heading rather than vanishing, so the
// twelve rows still add up to everything the group spent.
const FALLBACK_INDEX = CATEGORY_GROUPS.length - 1;

/** Per currency, one sum per top-level category group, in `CATEGORY_GROUPS`
 *  order — always all twelve, zeros included, so a pasted column lines up
 *  with the same rows every month. Currencies come out alphabetically and are
 *  never added together (the app holds no exchange rates). */
export function summarizeByGroup(totals: readonly CategoryTotal[]): Map<string, bigint[]> {
  const out = new Map<string, bigint[]>();
  for (const { category, currency, total } of [...totals].sort((a, b) =>
    a.currency.localeCompare(b.currency),
  )) {
    let sums = out.get(currency);
    if (!sums) {
      sums = CATEGORY_GROUPS.map(() => 0n);
      out.set(currency, sums);
    }
    sums[GROUP_INDEX.get(category) ?? FALLBACK_INDEX] += toUnits(total);
  }
  return out;
}

/** The clipboard text: one plain number per line, at the currency's own
 *  precision, no grouping and no currency code — anything else makes a
 *  spreadsheet paste text instead of numbers. The decimal separator follows
 *  the app's language, the best guess available here at the spreadsheet's:
 *  a Polish Excel reads "120.50" as text (or a date), an English one reads
 *  "120,50" as text. */
export function spreadsheetColumn(
  sums: readonly bigint[],
  currency: string,
  lang: "en" | "pl",
): string {
  const precision = precisionFor(currency);
  const sep = lang === "pl" ? "," : ".";
  return sums
    .map((units) => {
      const [intPart, frac] = fromUnits(units).split(".");
      return precision > 0 ? `${intPart}${sep}${frac.slice(0, precision)}` : intPart;
    })
    .join("\n");
}
