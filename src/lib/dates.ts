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

export function formatDateOnly(dateStr: string, locale: string): string {
  // Appending a time makes the Date constructor parse in *local* time.
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale);
}
