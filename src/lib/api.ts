import { supabase } from "./supabase";

const API_BASE: string = import.meta.env.VITE_API_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
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
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (payload.detail) detail = JSON.stringify(payload.detail);
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
