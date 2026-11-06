import { describe, expect, it } from "vitest";
import { CATEGORY_GROUPS } from "./categories";
import { fromUnits, spreadsheetColumn, summarizeByGroup } from "./categorySummary";

const row = (category: string, total: string, currency = "PLN") => ({ category, currency, total });

describe("summarizeByGroup", () => {
  it("folds categories into the twelve groups, zeros included, in list order", () => {
    const out = summarizeByGroup([
      row("Groceries", "10.1000"),
      row("Dining out", "0.2000"),
      row("Rent", "2000.0000"),
      row("General", "1.0000"),
    ]);
    const sums = out.get("PLN")!;
    expect(sums).toHaveLength(12);
    expect(CATEGORY_GROUPS).toHaveLength(12);
    expect(sums.map(fromUnits)).toEqual([
      "10.3000", // Food and drink: 10.10 + 0.20, exactly — no float drift
      "0.0000", "0.0000", "0.0000", "0.0000", "0.0000", "0.0000", "0.0000", "0.0000",
      "2000.0000", // Home and appliances
      "0.0000",
      "1.0000", // Uncategorized
    ]);
  });

  it("keeps currencies apart, alphabetically", () => {
    const out = summarizeByGroup([row("Taxi", "5.0000", "PLN"), row("Taxi", "3.0000", "EUR")]);
    expect([...out.keys()]).toEqual(["EUR", "PLN"]);
    expect(fromUnits(out.get("EUR")![6])).toBe("3.0000");
    expect(fromUnits(out.get("PLN")![6])).toBe("5.0000");
  });

  it("puts a category this bundle does not know under the last heading", () => {
    const sums = summarizeByGroup([row("Something new", "7.0000")]).get("PLN")!;
    expect(fromUnits(sums[11])).toBe("7.0000");
  });

  it("returns nothing for a month with no expenses", () => {
    expect(summarizeByGroup([]).size).toBe(0);
  });
});

describe("spreadsheetColumn", () => {
  const sums = [123456n, 0n, 20000000n]; // 12.3456 is impossible in practice, but shows truncation to precision

  it("writes one plain number per line, no grouping or currency code", () => {
    expect(spreadsheetColumn(sums, "PLN", "en")).toBe("12.34\n0.00\n2000.00");
  });

  it("uses a decimal comma in Polish", () => {
    expect(spreadsheetColumn(sums, "PLN", "pl")).toBe("12,34\n0,00\n2000,00");
  });

  it("follows the currency's precision", () => {
    expect(spreadsheetColumn([15000000n, 0n], "JPY", "pl")).toBe("1500\n0");
    expect(spreadsheetColumn([12345n], "KWD", "en")).toBe("1.234");
  });
});
