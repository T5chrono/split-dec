import { describe, expect, it, vi } from "vitest";
import { formatDateOnly, parseLocalISO, toLocalISO, todayLocalISO } from "./dates";

describe("toLocalISO / parseLocalISO", () => {
  it("round-trips a local date without shifting day", () => {
    const d = new Date(2026, 5, 20); // June 20, local time
    expect(toLocalISO(d)).toBe("2026-06-20");
    expect(toLocalISO(parseLocalISO("2026-06-20"))).toBe("2026-06-20");
  });

  it("pads single-digit months and days", () => {
    expect(toLocalISO(new Date(2026, 0, 5))).toBe("2026-01-05");
  });
});

describe("todayLocalISO", () => {
  it("matches the system clock's local calendar day, not UTC's", () => {
    // Pin the clock to a moment that is a different calendar day in UTC
    // than in a negative-UTC-offset timezone (this is the exact bug the
    // PR review caught: new Date().toISOString() reports the wrong day).
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 20, 23, 30)); // June 20, 23:30 local
    expect(todayLocalISO()).toBe("2026-06-20");
    vi.useRealTimers();
  });
});

describe("formatDateOnly", () => {
  it("does not shift the day when formatting for display", () => {
    // Regression: new Date("2026-06-20") parses as UTC midnight, which
    // renders as June 19 in negative-UTC-offset locales.
    const formatted = formatDateOnly("2026-06-20", "en-US");
    expect(formatted).toContain("20");
    expect(formatted).not.toContain("19");
  });
});
