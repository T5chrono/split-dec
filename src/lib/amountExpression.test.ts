import { describe, expect, it } from "vitest";
import {
  MAX_EXPRESSION_LENGTH,
  evaluateAmountExpression,
  isAmountExpression,
  resolveAmountInput,
} from "./amountExpression";

const ok = (raw: string, currency = "PLN") => {
  const r = evaluateAmountExpression(raw, currency);
  if (!r.ok) throw new Error(`expected ${raw} to evaluate, got ${r.error}`);
  return r.amount;
};
const err = (raw: string, currency = "PLN") => {
  const r = evaluateAmountExpression(raw, currency);
  return r.ok ? `ok:${r.amount}` : r.error;
};

describe("evaluateAmountExpression", () => {
  it("adds two receipts with mixed decimal separators", () => {
    expect(ok("20.45 + 16,78")).toBe("37.23");
  });

  it("is exact where binary floats are not", () => {
    expect(ok("0.1 + 0.2")).toBe("0.30");
    expect(ok("0,1+0,2", "KWD")).toBe("0.300");
    expect(ok("1.1 * 1.1 * 1.1")).toBe("1.33"); // 1.331, float gives 1.3310000000000004
  });

  it("respects precedence and parentheses", () => {
    expect(ok("2 + 3 * 4")).toBe("14.00");
    expect(ok("(2 + 3) * 4")).toBe("20.00");
    expect(ok("10 - 4 - 3")).toBe("3.00"); // left-associative
    expect(ok("100 / 5 / 2")).toBe("10.00");
    expect(ok("((1 + 2) * (3 + 4)) / 7")).toBe("3.00");
  });

  it("handles unary minus", () => {
    expect(ok("-5 + 10")).toBe("5.00");
    expect(ok("10 - -5")).toBe("15.00");
    expect(ok("-(2 - 7)")).toBe("5.00");
  });

  it("ignores whitespace", () => {
    expect(ok("  1 +\t2  ")).toBe("3.00");
  });

  it("divides exactly and rounds once, half-to-even, at the currency's precision", () => {
    expect(ok("100 / 3")).toBe("33.33");
    expect(ok("200 / 3")).toBe("66.67");
    // Ties: 0.125 → 0.12, 0.135 → 0.14 (the even neighbour), as in splits.py.
    expect(ok("0.25 / 2")).toBe("0.12");
    expect(ok("0.27 / 2")).toBe("0.14");
    // Rounding happens on the exact result, not per step: 1/3*3 is exactly 1.
    expect(ok("1 / 3 * 3")).toBe("1.00");
  });

  it("rounds per currency: JPY 0, PLN 2, KWD 3", () => {
    expect(ok("1000 / 3", "JPY")).toBe("333");
    expect(ok("2.5 + 0", "JPY")).toBe("2"); // tie → even
    expect(ok("3.5 + 0", "JPY")).toBe("4");
    expect(ok("10 / 3", "KWD")).toBe("3.333");
    expect(ok("10 / 3", "PLN")).toBe("3.33");
  });

  it("refuses division by zero, including by a zero subexpression", () => {
    expect(err("5 / 0")).toBe("amountExprDivByZero");
    expect(err("5 / (2 - 2)")).toBe("amountExprDivByZero");
    expect(err("5 / 0,00")).toBe("amountExprDivByZero");
  });

  it("refuses a negative result", () => {
    expect(err("5 - 10")).toBe("amountExprNegative");
    expect(err("-3")).toBe("amountExprNegative");
  });

  it("refuses garbage", () => {
    for (const raw of [
      "",
      "+",
      "1 +",
      "* 2",
      "1 + + 2", // no unary plus
      "(1 + 2",
      "1 + 2)",
      "()",
      "1 2",
      "1..2",
      "1,2,3",
      "12.",
      ".5 + 1",
      "1e3 + 1",
      "abc",
      "2 ^ 3",
      "alert(1)",
      "1 + 2; 3",
      "١ + ٢", // non-ASCII digits
    ]) {
      expect(err(raw), raw).toBe("amountExprInvalid");
    }
  });

  it("refuses over-long input before parsing it", () => {
    const long = Array(MAX_EXPRESSION_LENGTH).fill("1").join("+");
    expect(long.length).toBeGreaterThan(MAX_EXPRESSION_LENGTH);
    expect(err(long)).toBe("amountExprTooLong");
    // Deep nesting inside the limit is still fine — no recursion blow-up.
    const depth = Math.floor((MAX_EXPRESSION_LENGTH - 1) / 2);
    expect(ok("(".repeat(depth) + "1" + ")".repeat(depth))).toBe("1.00");
  });

  it("stays exact on large numbers", () => {
    expect(ok("9999999999.99 + 0.01")).toBe("10000000000.00");
    expect(ok("123456789.12 * 3")).toBe("370370367.36");
  });
});

describe("isAmountExpression", () => {
  it("is false for a plain number or text without an operator", () => {
    for (const raw of ["", "  ", "12", "12,50", " 12.50 ", "12.", "abc"]) {
      expect(isAmountExpression(raw), raw).toBe(false);
    }
  });

  it("is true once an operator or parenthesis appears", () => {
    for (const raw of ["1+2", "20.45 + 16,78", "-5", "(3)", "4/2", "2*3"]) {
      expect(isAmountExpression(raw), raw).toBe(true);
    }
  });
});

describe("resolveAmountInput", () => {
  it("treats a plain number exactly as before", () => {
    expect(resolveAmountInput("12,50", "PLN")).toEqual({
      amount: "12.50",
      error: null,
      isExpression: false,
    });
    expect(resolveAmountInput("10.123", "PLN").error).toBe("amountTooPrecise");
    expect(resolveAmountInput("", "PLN")).toEqual({
      amount: null,
      error: null,
      isExpression: false,
    });
  });

  it("returns the computed amount for an expression", () => {
    expect(resolveAmountInput("20.45 + 16,78", "PLN")).toEqual({
      amount: "37.23",
      error: null,
      isExpression: true,
    });
  });

  it("runs the result through the ordinary amount rules", () => {
    expect(resolveAmountInput("5 - 5", "PLN").error).toBe("amountNotPositive");
    expect(resolveAmountInput("0.001 * 1", "PLN").error).toBe("amountNotPositive"); // rounds to 0.00
    expect(resolveAmountInput("99999999999 + 1", "PLN").error).toBe("amountTooLarge");
    expect(resolveAmountInput("1 / 0", "PLN")).toEqual({
      amount: null,
      error: "amountExprDivByZero",
      isExpression: true,
    });
  });
});
