import { afterEach, describe, expect, it, vi } from "vitest";
import {
  formatDateOnly,
  monthRange,
  parseLocalISO,
  shiftMonthISO,
  toLocalISO,
  toMonthISO,
  todayLocalISO,
} from "./dates";

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
  afterEach(() => vi.useRealTimers());

  it("matches the system clock's local calendar day, not UTC's", () => {
    // Pin the clock to a moment that is a different calendar day in UTC
    // than in a negative-UTC-offset timezone (this is the exact bug the
    // PR review caught: new Date().toISOString() reports the wrong day).
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 20, 23, 30)); // June 20, 23:30 local
    expect(todayLocalISO()).toBe("2026-06-20");
  });
});

describe("month helpers", () => {
  it("gives the first and last day of a month, leap years included", () => {
    expect(monthRange("2026-10")).toEqual({ from: "2026-10-01", to: "2026-10-31" });
    expect(monthRange("2026-02")).toEqual({ from: "2026-02-01", to: "2026-02-28" });
    expect(monthRange("2028-02")).toEqual({ from: "2028-02-01", to: "2028-02-29" });
    expect(monthRange("2026-12")).toEqual({ from: "2026-12-01", to: "2026-12-31" });
  });

  it("steps across year boundaries", () => {
    expect(shiftMonthISO("2026-01", -1)).toBe("2025-12");
    expect(shiftMonthISO("2026-12", 1)).toBe("2027-01");
  });

  it("reads the month off the local calendar day", () => {
    expect(toMonthISO(new Date(2026, 9, 31, 23, 30))).toBe("2026-10");
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
