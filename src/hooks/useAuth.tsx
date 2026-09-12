import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabase";
import { reportError } from "../lib/monitoring";

interface AuthState {
  session: Session | null;
  loading: boolean;
  /** True from PASSWORD_RECOVERY until the password is updated (or sign-out). */
  passwordRecovery: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  /** Throws AuthError. `needsConfirmation` is true whenever no session came
   *  back — including the obfuscated already-registered response under
   *  enumeration protection, which must stay indistinguishable. */
  signUpWithPassword: (
    email: string,
    password: string,
    fullName: string,
  ) => Promise<{ needsConfirmation: boolean }>;
  /** Throws AuthError (invalid_credentials, email_not_confirmed, …). */
  signInWithPassword: (email: string, password: string) => Promise<void>;
  /** Throws AuthError (over_email_send_rate_limit, …). */
  requestPasswordReset: (email: string) => Promise<void>;
  /** Throws AuthError (weak_password, same_password, …). On success it also
   *  revokes the user's *other* sessions — see the implementation. */
  updatePassword: (newPassword: string) => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  session: null,
  loading: true,
  passwordRecovery: false,
  signInWithGoogle: async () => {},
  signOut: async () => {},
  signUpWithPassword: async () => ({ needsConfirmation: false }),
  signInWithPassword: async () => {},
  requestPasswordReset: async () => {},
  updatePassword: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [passwordRecovery, setPasswordRecovery] = useState(false);
  const queryClient = useQueryClient();
  const lastUserId = useRef<string | null>(null);

  useEffect(() => {
    // Query keys are not user-scoped, so the cache MUST be dropped whenever
    // the authenticated user changes (sign-out, or a different account
    // signing in on the same browser) — otherwise user B briefly sees user
    // A's cached groups/expenses/balances. Token refreshes keep the same
    // user id and don't clear anything.
    const applySession = (s: Session | null) => {
      const userId = s?.user.id ?? null;
      if (userId !== lastUserId.current) {
        queryClient.clear();
        lastUserId.current = userId;
      }
      setSession(s);
    };

    supabase.auth.getSession().then(({ data }) => {
      applySession(data.session);
      setLoading(false);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((event, s) => {
      if (event === "PASSWORD_RECOVERY") setPasswordRecovery(true);
      if (event === "SIGNED_OUT") setPasswordRecovery(false);
      applySession(s);
    });
    return () => sub.subscription.unsubscribe();
  }, [queryClient]);

  const signInWithGoogle = async () => {
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin },
    });
  };

  const signOut = async () => {
    const { error } = await supabase.auth.signOut();
    if (error) {
      // Reaching here does *not* mean the session survived: the SDK removes it
      // locally on every path — 401/403/404 are swallowed on purpose, and any
      // other error still clears the session before returning it. What failed
      // is the revocation at Supabase, so the refresh token stays usable
      // wherever else it is held. Nothing else in the app would ever say so.
      reportError(error);
      // The cache is ours rather than the SDK's, and it only empties because
      // `_removeSession` emits SIGNED_OUT. That is one library version away
      // from not being true, and the failure mode — the next person on this
      // browser rendering from the last person's cached groups and balances —
      // is the one thing here we can close without asking the SDK anything.
      // `tests/../useAuth.test.tsx` pins the SDK half; this is the half that
      // does not depend on it.
      queryClient.clear();
      lastUserId.current = null;
    }
  };

  const signUpWithPassword = async (
    email: string,
    password: string,
    fullName: string,
  ) => {
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        // The handle_new_user DB trigger reads full_name from the signup
        // metadata — email signups have no OAuth profile to fall back on.
        data: { full_name: fullName },
        emailRedirectTo: window.location.origin,
      },
    });
    if (error) throw error;
    return { needsConfirmation: data.session === null };
  };

  const signInWithPassword = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) throw error;
  };

  const requestPasswordReset = async (email: string) => {
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });
    if (error) throw error;
  };

  const updatePassword = async (newPassword: string) => {
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    if (error) throw error;
    // Changing a password is what somebody does when they believe another
    // person is in their account, and Supabase does not act on that belief:
    // `UpdateUser` writes the new password and never touches the session
    // table, so the other party keeps a refresh token that goes on minting
    // access tokens indefinitely. Without this call the one gesture people
    // reach for in that moment is the one that does nothing.
    //
    // `scope: "others"` revokes every session except this one — the SDK skips
    // its own `_removeSession` for that scope — so whoever just set the
    // password stays signed in here while everyone else is turned out. That
    // includes their own other devices, which is the intent rather than a
    // side effect.
    //
    // Its failure is reported, never thrown. The password has already changed
    // by this point, so throwing would tell the caller it had not; a
    // revocation lost to a flaky network leaves the other sessions exactly
    // where they were a second earlier, which is bad but not worse.
    const { error: revokeError } = await supabase.auth.signOut({ scope: "others" });
    if (revokeError) reportError(revokeError);
    setPasswordRecovery(false);
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        passwordRecovery,
        signInWithGoogle,
        signOut,
        signUpWithPassword,
        signInWithPassword,
        requestPasswordReset,
        updatePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
