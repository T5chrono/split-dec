import { AuthError } from "@supabase/supabase-js";
import type { TKey } from "./i18n";

// Must match the "Minimum password length" setting in the Supabase dashboard —
// otherwise the client accepts passwords the server rejects (or vice versa).
export const MIN_PASSWORD_LENGTH = 8;

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
