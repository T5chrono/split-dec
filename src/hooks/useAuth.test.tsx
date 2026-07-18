import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import { AuthProvider, useAuth } from "./useAuth";
import { createTestQueryClient } from "../test/utils";

// Controllable supabase auth: tests drive session changes through the
// captured onAuthStateChange callback.
let authCallback: ((event: string, session: Session | null) => void) | null = null;
vi.mock("../lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn((cb) => {
        authCallback = cb;
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      }),
      signInWithOAuth: vi.fn(),
      signOut: vi.fn(),
      signUp: vi.fn().mockResolvedValue({ data: { session: null, user: null }, error: null }),
      signInWithPassword: vi.fn().mockResolvedValue({ data: {}, error: null }),
      resetPasswordForEmail: vi.fn().mockResolvedValue({ data: {}, error: null }),
      updateUser: vi.fn().mockResolvedValue({ data: {}, error: null }),
    },
  },
}));
import { supabase } from "../lib/supabase";

const sessionFor = (userId: string) => ({ user: { id: userId } }) as Session;

// Captures the context value so tests can call the auth methods and read
// passwordRecovery as the provider re-renders.
let auth: ReturnType<typeof useAuth>;
function Capture() {
  auth = useAuth();
  return null;
}

function renderAuth() {
  const queryClient = createTestQueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <Capture />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return queryClient;
}

beforeEach(() => {
  authCallback = null;
});

describe("AuthProvider — query cache isolation between users", () => {
  it("clears cached queries when a different user signs in", async () => {
    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <div />
        </AuthProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(authCallback).not.toBeNull());

    // User A signs in and accumulates cached data.
    act(() => authCallback!("SIGNED_IN", sessionFor("user-a")));
    queryClient.setQueryData(["groups"], [{ id: "g1", name: "A's group" }]);
    expect(queryClient.getQueryData(["groups"])).toBeDefined();

    // A token refresh for the same user must NOT clear the cache.
    act(() => authCallback!("TOKEN_REFRESHED", sessionFor("user-a")));
    expect(queryClient.getQueryData(["groups"])).toBeDefined();

    // User B signs in on the same browser: user A's data must be gone.
    act(() => authCallback!("SIGNED_IN", sessionFor("user-b")));
    expect(queryClient.getQueryData(["groups"])).toBeUndefined();
  });

  it("clears cached queries on sign-out", async () => {
    const queryClient = createTestQueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <div />
        </AuthProvider>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(authCallback).not.toBeNull());

    act(() => authCallback!("SIGNED_IN", sessionFor("user-a")));
    queryClient.setQueryData(["balances", "g1"], { PLN: [] });

    act(() => authCallback!("SIGNED_OUT", null));
    expect(queryClient.getQueryData(["balances", "g1"])).toBeUndefined();
  });

  it("clears the cache when a recovery link signs in a different user", async () => {
    const queryClient = renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    act(() => authCallback!("SIGNED_IN", sessionFor("user-a")));
    queryClient.setQueryData(["groups"], [{ id: "g1" }]);

    // User B opens their recovery link in user A's browser.
    act(() => {
      authCallback!("SIGNED_IN", sessionFor("user-b"));
      authCallback!("PASSWORD_RECOVERY", sessionFor("user-b"));
    });
    expect(queryClient.getQueryData(["groups"])).toBeUndefined();
    expect(auth.passwordRecovery).toBe(true);
  });
});

describe("AuthProvider — email/password methods", () => {
  it("signUpWithPassword passes full_name metadata and emailRedirectTo", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    const result = await auth.signUpWithPassword("a@b.com", "password123", "Ala Kot");
    expect(supabase.auth.signUp).toHaveBeenCalledWith({
      email: "a@b.com",
      password: "password123",
      options: {
        data: { full_name: "Ala Kot" },
        emailRedirectTo: window.location.origin,
      },
    });
    // No session back (confirmation pending OR obfuscated existing-user
    // response — deliberately indistinguishable).
    expect(result).toEqual({ needsConfirmation: true });
  });

  it("signUpWithPassword throws the supabase error", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    const boom = Object.assign(new Error("weak"), { code: "weak_password" });
    vi.mocked(supabase.auth.signUp).mockResolvedValueOnce({
      data: { session: null, user: null },
      error: boom,
    } as never);
    await expect(auth.signUpWithPassword("a@b.com", "short", "Ala")).rejects.toBe(boom);
  });

  it("signInWithPassword throws the supabase error", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    const boom = Object.assign(new Error("nope"), { code: "invalid_credentials" });
    vi.mocked(supabase.auth.signInWithPassword).mockResolvedValueOnce({
      data: {},
      error: boom,
    } as never);
    await expect(auth.signInWithPassword("a@b.com", "wrong")).rejects.toBe(boom);
  });

  it("requestPasswordReset targets /reset-password", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    await auth.requestPasswordReset("a@b.com");
    expect(supabase.auth.resetPasswordForEmail).toHaveBeenCalledWith("a@b.com", {
      redirectTo: `${window.location.origin}/reset-password`,
    });
  });

  it("PASSWORD_RECOVERY sets the flag, updatePassword clears it", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());
    expect(auth.passwordRecovery).toBe(false);

    act(() => {
      authCallback!("SIGNED_IN", sessionFor("user-a"));
      authCallback!("PASSWORD_RECOVERY", sessionFor("user-a"));
    });
    expect(auth.passwordRecovery).toBe(true);

    await act(() => auth.updatePassword("newpassword1"));
    expect(supabase.auth.updateUser).toHaveBeenCalledWith({ password: "newpassword1" });
    expect(auth.passwordRecovery).toBe(false);
  });

  it("SIGNED_OUT clears the recovery flag", async () => {
    renderAuth();
    await waitFor(() => expect(authCallback).not.toBeNull());

    act(() => {
      authCallback!("SIGNED_IN", sessionFor("user-a"));
      authCallback!("PASSWORD_RECOVERY", sessionFor("user-a"));
    });
    expect(auth.passwordRecovery).toBe(true);

    act(() => authCallback!("SIGNED_OUT", null));
    expect(auth.passwordRecovery).toBe(false);
  });
});
