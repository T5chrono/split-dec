import { describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import type { Session } from "@supabase/supabase-js";
import { AuthProvider } from "./useAuth";
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
    },
  },
}));

const sessionFor = (userId: string) => ({ user: { id: userId } }) as Session;

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
});
