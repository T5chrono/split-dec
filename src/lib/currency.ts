// Mirrors the backend's ISO 4217 minor-unit lookup (api/_src/currencies.py).
const CURRENCY_PRECISION: Record<string, number> = {
  BIF: 0, CLP: 0, DJF: 0, GNF: 0, ISK: 0, JPY: 0, KMF: 0,
  KRW: 0, PYG: 0, RWF: 0, UGX: 0, UYI: 0, VND: 0, VUV: 0,
  XAF: 0, XOF: 0, XPF: 0,
  BHD: 3, IQD: 3, JOD: 3, KWD: 3, LYD: 3, OMR: 3, TND: 3,
};

export const precisionFor = (currency: string): number =>
  CURRENCY_PRECISION[currency.toUpperCase()] ?? 2;

// Locale-dependent decimal separator; kept in module state so formatMoney
// call sites stay simple. Set by I18nProvider on language change.
let decimalSep = ".";
export function setMoneyLocale(lang: "en" | "pl"): void {
  decimalSep = lang === "pl" ? "," : ".";
}

/** Format a backend money string (e.g. "120.5000") for display at the
 *  currency's own precision, without ever passing through a float total. */
export function formatMoney(amount: string, currency: string): string {
  const precision = precisionFor(currency);
  const negative = amount.startsWith("-");
  const [intPartRaw, fracRaw = ""] = amount.replace("-", "").split(".");
  const frac = fracRaw.padEnd(precision, "0").slice(0, precision);
  const intPart = intPartRaw.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const digits = precision > 0 ? `${intPart}${decimalSep}${frac}` : intPart;
  return `${negative ? "-" : ""}${digits} ${currency}`;
}

/** Normalize user-typed amounts: trims and accepts both comma and dot as
 *  the decimal separator ("12,50" -> "12.50"). */
export function normalizeAmountInput(raw: string): string {
  return raw.trim().replace(",", ".");
}

/** Shared input validation pattern allowing either separator. */
export const AMOUNT_PATTERN = "^\\d+([.,]\\d+)?$";

/** Trim a backend money string for use in an editable input: "30.0000" ->
 *  "30.00" (per the currency's precision; "100.0000" JPY -> "100"). */
export function trimAmount(amount: string, currency: string): string {
  const precision = precisionFor(currency);
  const negative = amount.startsWith("-");
  const [intPart, frac = ""] = amount.replace("-", "").split(".");
  const digits =
    precision === 0
      ? intPart
      : `${intPart}.${frac.padEnd(precision, "0").slice(0, precision)}`;
  return `${negative ? "-" : ""}${digits}`;
}

/** Parse a user-entered amount into integer minor units ("12,50" -> 1250 for
 *  a 2-decimal currency). Returns null for empty/invalid input. Integer math
 *  only — money never passes through binary floats. */
export function toMinorUnits(raw: string, currency: string): number | null {
  const normalized = normalizeAmountInput(raw);
  if (!/^\d+(\.\d+)?$/.test(normalized)) return null;
  const precision = precisionFor(currency);
  const [intPart, frac = ""] = normalized.split(".");
  if (frac.length > precision) return null; // more decimals than the currency allows
  return Number(intPart) * 10 ** precision + Number(frac.padEnd(precision, "0") || "0");
}

/** Format integer minor units back into an input-ready string (1250 -> "12.50"). */
export function fromMinorUnits(units: number, currency: string): string {
  const precision = precisionFor(currency);
  if (precision === 0) return String(units);
  const s = String(units).padStart(precision + 1, "0");
  return `${s.slice(0, -precision)}.${s.slice(-precision)}`;
}

export const COMMON_CURRENCIES = [
  "PLN", "EUR", "USD", "GBP", "CHF", "CZK", "SEK", "NOK", "DKK", "JPY",
  "AUD", "CAD", "HUF", "UAH", "KWD",
];

/** Why an amount a user typed cannot be sent, as an i18n key — or null when
 *  it is fine. Empty input is *not* an error here: the fields are `required`,
 *  so the browser handles the pristine case and a red line on an untouched
 *  form would be noise.
 *
 *  This mirrors the backend's Pydantic constraints (`gt=0`, NUMERIC(14,4),
 *  plus the per-currency precision check in `splits.py`) on purpose. Without
 *  it those violations came back as a raw 422 body and the user was shown
 *  `[{"type":"greater_than","loc":["body","total_amount"],…}]`. Keep the two
 *  in step: a rule that only exists here is a rule the API still rejects. */
export type AmountError =
  | "amountInvalid"
  | "amountNotPositive"
  | "amountNoDecimals"
  | "amountTooPrecise"
  | "amountTooLarge";

/** Integer digits NUMERIC(14,4) has room for once the 4 decimals are taken. */
const MAX_AMOUNT_INT_DIGITS = 10;

export function validateAmount(raw: string, currency: string): AmountError | null {
  const normalized = normalizeAmountInput(raw);
  if (normalized === "") return null;
  if (!/^\d+(\.\d+)?$/.test(normalized)) return "amountInvalid";
  const [intPart, frac = ""] = normalized.split(".");
  const precision = precisionFor(currency);
  if (frac.length > precision) return precision === 0 ? "amountNoDecimals" : "amountTooPrecise";
  if (intPart.replace(/^0+/, "").length > MAX_AMOUNT_INT_DIGITS) return "amountTooLarge";
  if (toMinorUnits(normalized, currency) === 0) return "amountNotPositive";
  return null;
}
