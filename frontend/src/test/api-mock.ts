import { vi } from "vitest";

type Reply = { status?: number; body?: unknown };
type Handler = (init: RequestInit & { url: string }) => Reply | Promise<Reply>;

/** Routes `fetch` by "METHOD /path"; unknown routes fail the test loudly. */
export function mockApi(routes: Record<string, Handler | Reply>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input), "http://localhost");
    const method = (init.method ?? "GET").toUpperCase();
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });
    const route = routes[`${method} ${path}`];
    if (!route) throw new Error(`Unexpected request: ${method} ${path}`);
    const reply = typeof route === "function" ? await route({ ...init, url: url.href }) : route;
    const status = reply.status ?? 200;
    return new Response(status === 204 ? null : JSON.stringify(reply.body ?? {}), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}

export const ME_STUDENT = {
  id: "00000000-0000-4000-8000-000000000001",
  login: "aliev.f",
  last_name: "Алиев",
  first_name: "Фарход",
  middle_name: "",
  full_name: "Алиев Фарход",
  initials: "ФА",
  roles: ["student"],
  active_role: "student",
  must_change_password: false,
  totp_enabled: false,
  totp_setup_required: false,
};

export const BRANDING = { center_name: "Учебный центр «Пример»", contacts: "+998 71 000 00 00" };
