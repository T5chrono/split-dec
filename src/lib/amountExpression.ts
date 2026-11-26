import { normalizeAmountInput, precisionFor, validateAmount, type AmountError } from "./currency";

/** Arithmetic in the amount field: `20.45 + 16,78` → `37.23`.
 *
 *  Two receipts for one expense are common enough that people otherwise add
 *  them up on a phone calculator and retype the result. This module turns the
 *  typed expression into the decimal string the API expects.
 *
 *  Two project rules shape it:
 *  - **No binary floats.** Every value is an exact rational (BigInt numerator
 *    over BigInt denominator), so `0.1 + 0.2` is exactly 3/10 and `/` loses
 *    nothing. The result is rounded once, at the end, to the currency's
 *    precision with round-half-even — the rounding `api/_src/splits.py` uses.
 *  - **No `eval` / `new Function`.** The CSP forbids both, so this is a
 *  tokenizer plus a recursive-descent parser over `+ - * /`, parentheses and
 *  unary minus. */

export type ExpressionError =
  | "amountExprInvalid"
  | "amountExprDivByZero"
  | "amountExprNegative"
  | "amountExprTooLong";

/** Long enough for a column of receipts, short enough that neither the parser's
 *  recursion nor the BigInt sizes can grow without bound. */
export const MAX_EXPRESSION_LENGTH = 200;

type Token =
  | { kind: "num"; n: bigint; d: bigint }
  | { kind: "op"; op: "+" | "-" | "*" | "/" }
  | { kind: "lparen" }
  | { kind: "rparen" };

/** A rational with d > 0, always reduced. */
type Rational = { n: bigint; d: bigint };

class ExprFailure extends Error {
  constructor(readonly code: ExpressionError) {
    super(code);
  }
}

const abs = (x: bigint) => (x < 0n ? -x : x);
function gcd(a: bigint, b: bigint): bigint {
  a = abs(a);
  b = abs(b);
  while (b !== 0n) [a, b] = [b, a % b];
  return a;
}
function reduce(n: bigint, d: bigint): Rational {
  if (d < 0n) {
    n = -n;
    d = -d;
  }
  const g = gcd(n, d);
  return g > 1n ? { n: n / g, d: d / g } : { n, d };
}

const NUMBER = /^\d+(?:[.,]\d+)?/;

function tokenize(src: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (/\s/.test(ch)) {
      i++;
      continue;
    }
    if (ch === "+" || ch === "-" || ch === "*" || ch === "/") {
      tokens.push({ kind: "op", op: ch });
      i++;
      continue;
    }
    if (ch === "(") {
      tokens.push({ kind: "lparen" });
      i++;
      continue;
    }
    if (ch === ")") {
      tokens.push({ kind: "rparen" });
      i++;
      continue;
    }
    const m = NUMBER.exec(src.slice(i));
    if (!m) throw new ExprFailure("amountExprInvalid");
    const [intPart, frac = ""] = m[0].replace(",", ".").split(".");
    const r = reduce(BigInt(intPart + frac), 10n ** BigInt(frac.length));
    tokens.push({ kind: "num", ...r });
    i += m[0].length;
  }
  return tokens;
}

/** expr   := term (('+' | '-') term)*
 *  term   := unary (('*' | '/') unary)*
 *  unary  := '-' unary | primary
 *  primary:= number | '(' expr ')' */
function parse(tokens: Token[]): Rational {
  let pos = 0;
  const peek = () => tokens[pos];

  const expr = (): Rational => {
    let left = term();
    for (let t = peek(); t?.kind === "op" && (t.op === "+" || t.op === "-"); t = peek()) {
      pos++;
      const right = term();
      left =
        t.op === "+"
          ? reduce(left.n * right.d + right.n * left.d, left.d * right.d)
          : reduce(left.n * right.d - right.n * left.d, left.d * right.d);
    }
    return left;
  };

  const term = (): Rational => {
    let left = unary();
    for (let t = peek(); t?.kind === "op" && (t.op === "*" || t.op === "/"); t = peek()) {
      pos++;
      const right = unary();
      if (t.op === "*") {
        left = reduce(left.n * right.n, left.d * right.d);
      } else {
        if (right.n === 0n) throw new ExprFailure("amountExprDivByZero");
        left = reduce(left.n * right.d, left.d * right.n);
      }
    }
    return left;
  };

  const unary = (): Rational => {
    const t = peek();
    if (t?.kind === "op" && t.op === "-") {
      pos++;
      const v = unary();
      return { n: -v.n, d: v.d };
    }
    return primary();
  };

  const primary = (): Rational => {
    const t = peek();
    if (t?.kind === "num") {
      pos++;
      return { n: t.n, d: t.d };
    }
    if (t?.kind === "lparen") {
      pos++;
      const v = expr();
      if (peek()?.kind !== "rparen") throw new ExprFailure("amountExprInvalid");
      pos++;
      return v;
    }
    throw new ExprFailure("amountExprInvalid");
  };

  const value = expr();
  if (pos !== tokens.length) throw new ExprFailure("amountExprInvalid");
  return value;
}

/** n/d rounded half-to-even to `precision` decimals, as integer minor units. */
function roundHalfEven({ n, d }: Rational, precision: number): bigint {
  const scaled = n * 10n ** BigInt(precision);
  const q = scaled / d; // truncates toward zero; callers pass n >= 0
  const r2 = (scaled % d) * 2n;
  if (r2 > d || (r2 === d && q % 2n === 1n)) return q + 1n;
  return q;
}

function unitsToDecimal(units: bigint, precision: number): string {
  if (precision === 0) return units.toString();
  const s = units.toString().padStart(precision + 1, "0");
  return `${s.slice(0, -precision)}.${s.slice(-precision)}`;
}

const PLAIN_NUMBER = /^\d+(?:[.,]\d+)?$/;

/** True when the field holds arithmetic rather than one plain number — the
 *  moment the form starts showing a result and stops applying the plain
 *  amount rules to the raw text. Anything else (a plain number, or text with
 *  no operator at all) is left to `validateAmount`, so a plain number behaves
 *  exactly as it did before expressions existed. */
export function isAmountExpression(raw: string): boolean {
  const s = raw.trim();
  return s !== "" && !PLAIN_NUMBER.test(s) && /[-+*/()]/.test(s);
}

export type ExpressionResult =
  | { ok: true; amount: string }
  | { ok: false; error: ExpressionError };

/** Evaluate an arithmetic amount for `currency`, returning a decimal string at
 *  the currency's precision ("37.23"; JPY "1235"; KWD "1.235"). A negative
 *  result is refused here; zero and over-large results come back as amounts
 *  and are left to `validateAmount`, which already words those cases. */
export function evaluateAmountExpression(raw: string, currency: string): ExpressionResult {
  if (raw.length > MAX_EXPRESSION_LENGTH) return { ok: false, error: "amountExprTooLong" };
  try {
    const value = parse(tokenize(raw));
    if (value.n < 0n) return { ok: false, error: "amountExprNegative" };
    const precision = precisionFor(currency);
    return { ok: true, amount: unitsToDecimal(roundHalfEven(value, precision), precision) };
  } catch (e) {
    if (e instanceof ExprFailure) return { ok: false, error: e.code };
    throw e;
  }
}

export type ResolvedAmount = {
  /** The decimal string to send, or null while the input cannot be sent. */
  amount: string | null;
  /** Why it cannot be sent, as an i18n key — null when it can (or is empty). */
  error: AmountError | ExpressionError | null;
  /** Whether the field holds arithmetic, i.e. whether to show a result. */
  isExpression: boolean;
};

/** What the expense form's amount field means: for a plain number exactly
 *  what it meant before (`normalizeAmountInput` + `validateAmount`), for an
 *  expression its rounded result, run through the same amount rules. */
export function resolveAmountInput(raw: string, currency: string): ResolvedAmount {
  if (!isAmountExpression(raw)) {
    const error = validateAmount(raw, currency);
    const normalized = normalizeAmountInput(raw);
    return { amount: error || normalized === "" ? null : normalized, error, isExpression: false };
  }
  const result = evaluateAmountExpression(raw, currency);
  if (!result.ok) return { amount: null, error: result.error, isExpression: true };
  const error = validateAmount(result.amount, currency);
  return { amount: error ? null : result.amount, error, isExpression: true };
}
