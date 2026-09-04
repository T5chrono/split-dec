import { afterEach, describe, expect, it, vi } from "vitest";
import { detailToMessage } from "./api";

// api.ts constructs the supabase client on import; the request path only needs
// `getSession`, and a stub keeps these tests off the network.
vi.mock("./supabase", () => ({
  supabase: { auth: { getSession: async () => ({ data: { session: null } }) } },
}));

describe("detailToMessage", () => {
  it("passes a plain FastAPI detail string through", () => {
    expect(detailToMessage("Percentages must sum to 100")).toBe("Percentages must sum to 100");
  });

  it("keeps only the readable half of a Pydantic 422 body", () => {
    const detail = [
      {
        type: "greater_than",
        loc: ["body", "total_amount"],
        msg: "Input should be greater than 0",
        input: "0000.00",
        ctx: { gt: 0 },
      },
    ];
    expect(detailToMessage(detail)).toBe("Input should be greater than 0.");
  });

  it("joins several errors and drops duplicates", () => {
    const detail = [
      { loc: ["body", "splits", 0, "amount"], msg: "Input should be greater than 0" },
      { loc: ["body", "splits", 1, "amount"], msg: "Input should be greater than 0" },
      { loc: ["body", "currency"], msg: "String should match pattern" },
    ];
    expect(detailToMessage(detail)).toBe(
      "Input should be greater than 0. String should match pattern.",
    );
  });

  it("returns null when there is nothing readable, so the caller keeps its fallback", () => {
    expect(detailToMessage(undefined)).toBeNull();
    expect(detailToMessage("")).toBeNull();
    expect(detailToMessage([])).toBeNull();
    expect(detailToMessage([{ type: "greater_than", loc: ["body"] }])).toBeNull();
    expect(detailToMessage({ code: 42 })).toBeNull();
  });
});

describe("API_BASE", () => {
  /** The URL `api.get` actually dials, with whatever env is currently stubbed.
   *  `resetModules` matters: API_BASE is computed once at module load, so the
   *  module has to be re-evaluated after each stub. */
  const requestedUrl = async (): Promise<string> => {
    // The parameters are declared rather than inferred: without them the mock's
    // call tuple is empty and `calls[0][0]` does not type-check.
    const fetchMock = vi.fn(
      async (_url: string, _init?: RequestInit) =>
        ({ ok: true, status: 200, json: async () => ({}) }) as unknown as Response,
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.resetModules();
    const { api } = await import("./api");
    await api.get("/groups");
    return fetchMock.mock.calls[0]![0];
  };

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.resetModules();
  });

  it("honours VITE_API_URL in a dev build, which is the only thing it is for", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_API_URL", "http://localhost:8000/api");
    expect(await requestedUrl()).toBe("http://localhost:8000/api/groups");
  });

  it("ignores VITE_API_URL entirely outside a dev build", async () => {
    /** The guardrail. VITE_API_URL is a build-time value on requests that
     *  carry the user's Supabase access token, so a production build that
     *  honoured it would ship an app mailing bearer tokens to whatever host an
     *  environment variable named — a redirect that never appears in a diff.
     *  Vite inlines `import.meta.env.DEV` as a literal, so in a real build the
     *  other branch is dead-code-eliminated and the value cannot even reach
     *  the bundle; this asserts the logic that makes that true. */
    vi.stubEnv("DEV", false);
    vi.stubEnv("VITE_API_URL", "https://attacker.example/api");
    expect(await requestedUrl()).toBe("/api/groups");
  });

  it("falls back to same-origin in a dev build with nothing configured", async () => {
    vi.stubEnv("DEV", true);
    vi.stubEnv("VITE_API_URL", "");
    expect(await requestedUrl()).toBe("/api/groups");
  });
});
