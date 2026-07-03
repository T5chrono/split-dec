/** Date-only ("YYYY-MM-DD") helpers. These must never round-trip through
 *  UTC (`toISOString`, `new Date("YYYY-MM-DD")`): that shifts the calendar
 *  day for users west of UTC (and the default day east of it). */

export function todayLocalISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

export function formatDateOnly(dateStr: string, locale: string): string {
  // Appending a time makes the Date constructor parse in *local* time.
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString(locale);
}
