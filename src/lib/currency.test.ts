import { afterEach, describe, expect, it } from "vitest";
import {
  formatMoney,
  fromMinorUnits,
  normalizeAmountInput,
  precisionFor,
  setMoneyLocale,
  toMinorUnits,
  validateAmount,
  trimAmount,
} from "./currency";

afterEach(() => setMoneyLocale("en"));

describe("precisionFor", () => {
  it("defaults to 2 decimals", () => {
    expect(precisionFor("PLN")).toBe(2);
  });

  it("knows 0-decimal currencies", () => {
    expect(precisionFor("JPY")).toBe(0);
  });

  it("is case-insensitive", () => {
    // Lowercase must still hit the 0-decimal entry, not fall through to the
    // ?? 2 default (which "usd"/"pln" would pass regardless of casing).
    expect(precisionFor("jpy")).toBe(0);
  });

  it("knows 3-decimal currencies", () => {
    expect(precisionFor("KWD")).toBe(3);
  });
});

describe("formatMoney", () => {
  it("formats a standard 2-decimal amount", () => {
    expect(formatMoney("120.5000", "USD")).toBe("120.50 USD");
  });

  it("truncates to the currency's precision, not the backend's 4 decimals", () => {
    expect(formatMoney("120.5678", "USD")).toBe("120.56 USD");
  });

  it("drops the decimal point entirely for 0-decimal currencies", () => {
    expect(formatMoney("100.0000", "JPY")).toBe("100 JPY");
  });

  it("keeps 3 decimals for KWD", () => {
    expect(formatMoney("10.3340", "KWD")).toBe("10.334 KWD");
  });

  it("preserves a negative sign", () => {
    expect(formatMoney("-45.0000", "EUR")).toBe("-45.00 EUR");
  });

  it("adds thousands separators", () => {
    expect(formatMoney("1234567.0000", "PLN")).toBe("1 234 567.00 PLN");
  });

  it("uses a comma decimal separator in Polish locale", () => {
    setMoneyLocale("pl");
    expect(formatMoney("120.5000", "PLN")).toBe("120,50 PLN");
  });
});

describe("normalizeAmountInput", () => {
  it("converts a comma decimal to a dot", () => {
    expect(normalizeAmountInput("12,50")).toBe("12.50");
  });

  it("leaves a dot decimal untouched", () => {
    expect(normalizeAmountInput("12.50")).toBe("12.50");
  });

  it("trims surrounding whitespace", () => {
    expect(normalizeAmountInput("  12,50  ")).toBe("12.50");
  });
});

describe("toMinorUnits / fromMinorUnits", () => {
  it("round-trips 2-decimal amounts through integer units", () => {
    expect(toMinorUnits("12.50", "USD")).toBe(1250);
    expect(toMinorUnits("12,50", "USD")).toBe(1250); // comma decimal accepted
    expect(fromMinorUnits(1250, "USD")).toBe("12.50");
  });

  it("respects currency precision", () => {
    expect(toMinorUnits("100", "JPY")).toBe(100);
    expect(fromMinorUnits(100, "JPY")).toBe("100");
    expect(toMinorUnits("10.334", "KWD")).toBe(10334);
    expect(fromMinorUnits(10334, "KWD")).toBe("10.334");
  });

  it("pads sub-unit values when formatting", () => {
    expect(fromMinorUnits(5, "USD")).toBe("0.05");
  });

  it("rejects invalid or over-precise input", () => {
    expect(toMinorUnits("", "USD")).toBeNull();
    expect(toMinorUnits("abc", "USD")).toBeNull();
    expect(toMinorUnits("1.2.3", "USD")).toBeNull();
    expect(toMinorUnits("10.123", "USD")).toBeNull(); // 3 decimals in a 2-decimal currency
    expect(toMinorUnits("100.5", "JPY")).toBeNull(); // fractional yen
  });
});

describe("trimAmount", () => {
  it("trims a 4-decimal backend string to 2 decimals", () => {
    expect(trimAmount("30.0000", "USD")).toBe("30.00");
  });

  it("trims to 0 decimals for JPY", () => {
    expect(trimAmount("100.0000", "JPY")).toBe("100");
  });

  it("trims to 3 decimals for KWD", () => {
    expect(trimAmount("10.3340", "KWD")).toBe("10.334");
  });

  it("preserves a negative sign", () => {
    expect(trimAmount("-30.0000", "USD")).toBe("-30.00");
  });
});

describe("validateAmount", () => {
  it("passes an ordinary amount and either separator", () => {
    expect(validateAmount("120.50", "PLN")).toBeNull();
    expect(validateAmount("120,50", "PLN")).toBeNull();
    expect(validateAmount("100", "JPY")).toBeNull();
    expect(validateAmount("10.334", "KWD")).toBeNull();
  });

  it("stays quiet while the field is still empty", () => {
    expect(validateAmount("", "PLN")).toBeNull();
    expect(validateAmount("   ", "PLN")).toBeNull();
  });

  it("rejects zero however it is written", () => {
    expect(validateAmount("0", "PLN")).toBe("amountNotPositive");
    expect(validateAmount("0000.00", "PLN")).toBe("amountNotPositive");
    expect(validateAmount("0,000", "KWD")).toBe("amountNotPositive");
    expect(validateAmount("0", "JPY")).toBe("amountNotPositive");
  });

  it("rejects unparseable input", () => {
    expect(validateAmount("abc", "PLN")).toBe("amountInvalid");
    expect(validateAmount("12.", "PLN")).toBe("amountInvalid");
    expect(validateAmount("-5", "PLN")).toBe("amountInvalid");
  });

  it("names the right precision problem per currency", () => {
    expect(validateAmount("10.123", "PLN")).toBe("amountTooPrecise");
    expect(validateAmount("100.5", "JPY")).toBe("amountNoDecimals");
    expect(validateAmount("10.3345", "KWD")).toBe("amountTooPrecise");
  });

  it("rejects amounts wider than NUMERIC(14,4), ignoring leading zeros", () => {
    expect(validateAmount("12345678901", "PLN")).toBe("amountTooLarge");
    expect(validateAmount("0001234567890", "PLN")).toBeNull();
  });
});
