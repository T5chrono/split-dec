import { supabase } from "./supabase";

/** Where the bearer token gets sent.
 *
 *  Same-origin `/api` in every build that is not a dev build, and no way to
 *  configure otherwise. `VITE_API_URL` is a *build-time* value baked into the
 *  bundle, so a production build that picked it up would ship an app that
 *  attaches the user's Supabase access token to requests aimed at whatever
 *  host that variable named — a redirect of every authenticated request, set
 *  by an environment variable rather than by code, and invisible in the diff.
 *  It exists for one reason (pointing `npm run dev` at a local uvicorn on
 *  :8000) and that reason only applies while `import.meta.env.DEV` is true.
 *
 *  Vite inlines `import.meta.env.DEV` as a literal, so in a production build
 *  this collapses to `"/api"` and the other branch is dropped entirely — the
 *  variable's value cannot end up in the bundle even if it is set. */
const API_BASE: string = import.meta.env.DEV ? import.meta.env.VITE_API_URL || "/api" : "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

/** FastAPI answers a schema violation with a *list* of Pydantic error objects,
 *  not a string. Stringifying it put
 *  `[{"type":"greater_than","loc":["body","total_amount"],…}]` in front of the
 *  user; keep only the human-readable `msg` fields. The forms validate the same
 *  rules before submitting, so this is the net under them rather than the
 *  primary path — anything reaching it is a rule the UI does not know about yet. */
export function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail.trim() || null;
  if (!Array.isArray(detail)) return null;
  const messages = detail
    .map((item) =>
      item && typeof item === "object" && typeof (item as { msg?: unknown }).msg === "string"
        ? (item as { msg: string }).msg.trim()
        : null,
    )
    .filter((msg): msg is string => msg !== null && msg !== "");
  if (messages.length === 0) return null;
  return [...new Set(messages)].map((m) => (/[.!?]$/.test(m) ? m : `${m}.`)).join(" ");
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; idempotencyKey?: string } = {},
): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const payload = await res.json();
      detail = detailToMessage(payload?.detail) ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown, idempotencyKey?: string) =>
    request<T>(path, { method: "POST", body, idempotencyKey }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export const newIdempotencyKey = () => crypto.randomUUID();
