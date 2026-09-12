import { AuthError } from "@supabase/supabase-js";
import type { TKey } from "./i18n";

/** Must match "Minimum password length" in the Supabase dashboard — otherwise
the client accepts passwords the server rejects, or turns away ones it would
have taken. It is the *whole* policy: "Password Requirements" there is left at
"No required characters" on purpose.

Length only, because required character classes get satisfied predictably —
`P@ssw0rd` meets all four and is in every cracking list — which is why NIST
SP 800-63B tells verifiers not to impose them. Twelve lowercase characters
already out-space eight from the full printable set by a wide margin.

The half of that guidance we cannot follow is the breach blocklist it assumes:
Supabase screens against HaveIBeenPwned only on the Pro plan, and this project
is on free. `docs/supply-chain.md` records the gap. If that ever changes and
character classes are turned on with it, `errWeakPassword` stops being true —
it names a length and nothing else. */
export const MIN_PASSWORD_LENGTH = 12;

// A courtesy cap on the signup name field, not a security boundary — and the
// difference matters. `full_name` never passes through our API: it goes into
// Supabase Auth's signup metadata and reaches `public.users` through the
// `handle_new_user` trigger, so anyone calling Auth directly with the
// publishable key bypasses this entirely. The real bounds are downstream and
// already in place: the invitation subject is normalized and cut to 200 UTF-8
// bytes (api/_src/emailer.py) and the HTML body is escaped. This exists so the
// form is honest about what a display name is for.
export const MAX_FULL_NAME_LENGTH = 100;

/** `name`, trimmed and cut to MAX_FULL_NAME_LENGTH characters.

`Array.from` rather than `slice`, which counts UTF-16 code units: an emoji or a
rarer CJK character is two units, so a plain `slice` landing between them stores
half a character in the signup metadata. Splitting by code point costs one
allocation on a value typed once per account.

It is still not grapheme-accurate — a flag or a family emoji is several code
points joined together and can be cut between them. Fixing that means
`Intl.Segmenter`, which is more machinery than a cosmetic cap on a form field is
worth. */
export function capFullName(name: string): string {
  const trimmed = name.trim();
  const points = Array.from(trimmed);
  return points.length <= MAX_FULL_NAME_LENGTH
    ? trimmed
    : points.slice(0, MAX_FULL_NAME_LENGTH).join("");
}

/** Whether `err` says the address already has an account.

Signup is the only place these codes appear, and the only safe answer to them
is the one a brand-new address gets — see the call site in `LoginPage`. They
are deliberately absent from `mapAuthError` below: there is no message to map
them to, because saying anything at all is the bug. */
export function isEmailAlreadyRegistered(err: unknown): boolean {
  const code = err instanceof AuthError ? err.code : undefined;
  return code === "user_already_exists" || code === "email_exists";
}

export function mapAuthError(err: unknown): TKey {
  const code = err instanceof AuthError ? err.code : undefined;
  switch (code) {
    case "invalid_credentials":
      return "errInvalidCredentials";
    case "email_not_confirmed":
      return "errEmailNotConfirmed";
    // "Secure password change" is on in the dashboard, so Supabase refuses a
    // password change from a session older than 24 hours unless the request
    // carries an emailed one-time code. We never send one — there is no
    // in-app change-password screen — so the only way to reach this is a
    // signed-in visitor typing /reset-password, which is precisely the case
    // the setting exists to refuse: whoever holds a stolen session should not
    // be able to lock the owner out of it. Sessions created by a recovery
    // link are exempt on Supabase's side, so the ordinary forgot-password
    // flow never lands here.
    case "reauthentication_needed":
      return "errReauthNeeded";
    case "weak_password":
      return "errWeakPassword";
    case "same_password":
      return "errSamePassword";
    case "over_email_send_rate_limit":
    case "over_request_rate_limit":
      return "errEmailRateLimit";
    case "validation_failed":
      return "errInvalidEmail";
    default:
      return "errAuthGeneric";
  }
}
