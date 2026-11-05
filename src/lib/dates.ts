/** Date-only ("YYYY-MM-DD") helpers. These must never round-trip through
 *  UTC (`toISOString`, `new Date("YYYY-MM-DD")`): that shifts the calendar
 *  day for users west of UTC (and the default day east of it). */

export function toLocalISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

export const todayLocalISO = (): string => toLocalISO(new Date());

export function parseLocalISO(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** "YYYY-MM" of the given day (local calendar). */
export const toMonthISO = (d: Date): string => toLocalISO(d).slice(0, 7);

/** "YYYY-MM" shifted by `delta` months. Built from day 1, so it never
 *  overflows the way Jan 31 + 1 month does. */
export function shiftMonthISO(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  return toMonthISO(new Date(y, m - 1 + delta, 1));
}

/** First and last calendar day of a "YYYY-MM" month, both inclusive. */
export function monthRange(month: string): { from: string; to: string } {
  const [y, m] = month.split("-").map(Number);
  return {
    from: toLocalISO(new Date(y, m - 1, 1)),
    to: toLocalISO(new Date(y, m, 0)), // day 0 of the next month = last of this
  };
}

export function formatDateOnly(dateStr: string, locale: string): string {
  // Appending a time makes the Date constructor parse in *local* time.
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale);
}
