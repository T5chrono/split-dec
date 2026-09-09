import { AuthError } from "@supabase/supabase-js";
import type { TKey } from "./i18n";

// Must match the "Minimum password length" setting in the Supabase dashboard —
// otherwise the client accepts passwords the server rejects (or vice versa).
export const MIN_PASSWORD_LENGTH = 8;

// A courtesy cap on the signup name field, not a security boundary — and the
// difference matters. `full_name` never passes through our API: it goes into
// Supabase Auth's signup metadata and reaches `public.users` through the
// `handle_new_user` trigger, so anyone calling Auth directly with the
// publishable key bypasses this entirely. The real bounds are downstream and
// already in place: the invitation subject is normalized and cut to 200 UTF-8
// bytes (api/_src/emailer.py) and the HTML body is escaped. This exists so the
// form is honest about what a display name is for.
export const MAX_FULL_NAME_LENGTH = 100;

export function mapAuthError(err: unknown): TKey {
  const code = err instanceof AuthError ? err.code : undefined;
  switch (code) {
    case "invalid_credentials":
      return "errInvalidCredentials";
    case "email_not_confirmed":
      return "errEmailNotConfirmed";
    // Only reachable if enumeration protection (Confirm email) is off.
    case "user_already_exists":
    case "email_exists":
      return "errEmailExists";
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
