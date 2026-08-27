import { useRef } from "react";
import { newIdempotencyKey } from "../lib/api";

/** One `Idempotency-Key` per entry being created, held across retries.
 *
 *  A retry that mints a fresh key is not a retry. If the first request reached
 *  the server and only its response was lost — a dropped connection, a phone
 *  going through a tunnel on the way back — a second request under a new key is
 *  a *different* entry as far as the server can tell, and the expense is
 *  recorded twice. The key is the client's way of saying "this is the entry I
 *  already asked you to record"; the create endpoints answer a replay with 200
 *  and the row they already have (api/_src/routers/expenses.py), which only
 *  works if the key survives the attempt that failed.
 *
 *  Scoped to the form's lifetime, which is what makes reuse safe: both forms
 *  close on success, so a key never carries over to a second, genuinely
 *  different entry. A rejected attempt keeps the key too, and that is
 *  harmless — the server stored nothing under it, so the corrected resubmit is
 *  the first entry that key ever names.
 */
export function useIdempotencyKey(): string {
  const key = useRef<string | null>(null);
  if (key.current === null) key.current = newIdempotencyKey();
  return key.current;
}
