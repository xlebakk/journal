import { apiRoot, isNativeApp, tokens } from "@/platform";

import type { components } from "./schema";

export type Schemas = components["schemas"];

const CSRF_COOKIE = "__Host-csrftoken";

/** Read on every request: Django rotates the token at login. */
function csrfToken(): string | undefined {
  const prefix = `${CSRF_COOKIE}=`;
  return document.cookie
    .split("; ")
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}

export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(status: number, data: unknown) {
    super(`API ${status}`);
    this.status = status;
    this.data = data;
  }

  /** Machine code from {"detail": "<code>"}, e.g. "invalid_credentials". */
  get code(): string | undefined {
    const detail = (this.data as { detail?: unknown } | null)?.detail;
    return typeof detail === "string" ? detail : undefined;
  }

  /** Field errors from a validation response: {"field": ["code", ...]}. */
  get fields(): Record<string, string[]> {
    if (!this.data || typeof this.data !== "object" || this.code) return {};
    const result: Record<string, string[]> = {};
    for (const [key, value] of Object.entries(this.data)) {
      if (Array.isArray(value)) result[key] = value.map(String);
    }
    return result;
  }

  field<T = unknown>(name: string): T | undefined {
    return (this.data as Record<string, T> | null)?.[name];
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

tokens.configure(`${apiRoot()}/auth/token/refresh`);

// The app's login and refresh calls carry no access token and must not trigger a refresh.
const TOKEN_FREE = /^\/auth\/(token|login)/;

function withQuery(path: string, query?: Record<string, string | undefined>): string {
  let url = `${apiRoot()}${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value) params.set(key, value);
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}

/**
 * fetch with the platform's credentials: the session cookie and CSRF token on the site, the
 * Bearer access token in the app. In the app a 401 refreshes the tokens once and repeats.
 */
async function send(path: string, init: RequestInit & { headers: Record<string, string> }) {
  const headers = { ...init.headers };
  if (!isNativeApp) {
    if (init.method && init.method !== "GET") {
      const token = csrfToken();
      if (token) headers["X-CSRFToken"] = token;
    }
    return fetch(path, { ...init, headers, credentials: "same-origin" });
  }
  const attempt = () => {
    const access = tokens.access();
    const auth: Record<string, string> = access ? { Authorization: `Bearer ${access}` } : {};
    return fetch(path, { ...init, headers: { ...headers, ...auth }, credentials: "omit" });
  };
  const relative = path.slice(apiRoot().length);
  if (TOKEN_FREE.test(relative)) return fetch(path, { ...init, headers, credentials: "omit" });
  const first = await attempt();
  if (first.status !== 401 || !(await tokens.refresh())) return first;
  return attempt();
}

export async function api<T>(
  path: string,
  options: { method?: Method; body?: unknown; query?: Record<string, string | undefined> } = {},
): Promise<T> {
  const { method = "GET", body, query } = options;
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const response = await send(withQuery(path, query), {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}

/** multipart/form-data upload (imports, the logo). */
export async function upload<T>(path: string, form: FormData): Promise<T> {
  const response = await send(withQuery(path), {
    method: "POST",
    headers: { Accept: "application/json" },
    body: form,
  });
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

function fileName(response: Response, fallback: string): string {
  const header = response.headers.get("Content-Disposition") ?? "";
  return /filename="([^"]+)"/.exec(header)?.[1] ?? fallback;
}

/** GET a file (XLSX/CSV export) and hand it to the browser as a download. */
export async function download(
  path: string,
  query: Record<string, string | undefined> = {},
): Promise<void> {
  const response = await send(withQuery(path, query), { method: "GET", headers: {} });
  if (!response.ok) {
    const data: unknown = await response.json().catch(() => null);
    throw new ApiError(response.status, data);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName(response, "export");
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
