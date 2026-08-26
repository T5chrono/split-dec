import { precisionFor, validateAmount } from "../lib/currency";
import { useI18n } from "../lib/i18n";

/** The one place an unsendable amount is turned into words. Both money forms
 *  use it to explain the problem *and* to hold the submit button, so the API
 *  never has to answer with its raw 422 body — which reached the user as
 *  `[{"type":"greater_than","loc":["body","total_amount"],…}]`.
 *  Returns null while the field is fine (or still empty). */
export function useAmountError(raw: string, currency: string): string | null {
  const { t } = useI18n();
  const key = validateAmount(raw, currency);
  if (!key) return null;
  return t(key)
    .replace("{currency}", currency)
    .replace("{n}", String(precisionFor(currency)));
}
