import { beforeEach, describe, expect, it, vi } from "vitest";
import { createClient } from "@supabase/supabase-js";

/** Does a *failed* sign-out still clear the session in this browser?
 *
 *  An external review said it might not: `useAuth.signOut` used to discard the
 *  SDK's error, so "the logout failed and the tokens are still here" would have
 *  looked exactly like success. Reading `@supabase/auth-js` says otherwise — it
 *  removes the local session on every path, including the one that returns an
 *  error — which is why that finding was closed rather than fixed.
 *
 *  That is an implementation detail, not a documented promise, and this
 *  codebase pins its dependencies but bumps them. So the reasoning the finding
 *  was closed on is asserted here against the real library rather than left in
 *  a review comment: if a future version returns the error *without* clearing,
 *  this fails, and someone gets to decide again with the facts in front of
 *  them.
 *
 *  Everything else about sign-out is tested against a mocked client in
 *  `src/hooks/useAuth.test.tsx`. A mock cannot answer this question, because
 *  the answer is the mock's assumption. */

const STORAGE_KEY = "sb-test-auth-token";

/** A JWT-shaped string. Never verified here — the SDK only reads `exp` out of
 *  it to decide whether the session needs refreshing before anything else. */
function fakeJwt(expiresInSeconds: number): string {
  const b64 = (o: object) =>
    btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  return [
    b64({ alg: "HS256", typ: "JWT" }),
    b64({
      sub: "00000000-0000-4000-8000-000000000000",
      aud: "authenticated",
      role: "authenticated",
      exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
    }),
    "signature",
  ].join(".");
}

let store: Record<string, string>;

const storage = {
  getItem: (k: string) => store[k] ?? null,
  setItem: (k: string, v: string) => void (store[k] = v),
  removeItem: (k: string) => void delete store[k],
};

beforeEach(() => {
  store = {
    [STORAGE_KEY]: JSON.stringify({
      access_token: fakeJwt(3600),
      refresh_token: "refresh-token",
      token_type: "bearer",
      expires_in: 3600,
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      user: { id: "00000000-0000-4000-8000-000000000000", aud: "authenticated" },
    }),
  };
});

/** A client whose only network call — the logout POST — fails. */
function clientWithFailingLogout() {
  const fetchImpl = vi.fn(async () =>
    new Response(JSON.stringify({ message: "boom" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const supabase = createClient("https://test.supabase.co", "publishable-key", {
    auth: {
      storage,
      storageKey: STORAGE_KEY,
      persistSession: true,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
    global: { fetch: fetchImpl as unknown as typeof fetch },
  });
  return { supabase, fetchImpl };
}

describe("supabase-js signOut, when the server refuses", () => {
  it("still removes the session from this browser", async () => {
    const { supabase, fetchImpl } = clientWithFailingLogout();
    expect(store[STORAGE_KEY]).toBeDefined();

    const { error } = await supabase.auth.signOut();

    expect(fetchImpl).toHaveBeenCalled(); // it really did try
    expect(error).not.toBeNull(); // and really did fail
    expect(store[STORAGE_KEY]).toBeUndefined(); // and cleared up anyway
    expect((await supabase.auth.getSession()).data.session).toBeNull();
  });
});
