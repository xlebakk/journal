import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// The Android app: Capacitor says «native», the Keystore is a map.
const keystore = new Map<string, string>();
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => true } }));
vi.mock("@capacitor/app", () => ({ App: { addListener: vi.fn(), exitApp: vi.fn() } }));
// Like a real Capacitor plugin: a Proxy that answers every property — `then` too. Resolving a
// promise with it hangs forever, which is how the first Android build got stuck.
vi.mock("capacitor-secure-storage-plugin", () => {
  const methods: Record<string, (options: { key: string; value?: string }) => Promise<unknown>> = {
    get: async ({ key }) => {
      if (!keystore.has(key)) throw new Error("missing");
      return { value: keystore.get(key) };
    },
    set: async ({ key, value }) => {
      keystore.set(key, value ?? "");
      return { value: true };
    },
    remove: async ({ key }) => {
      keystore.delete(key);
      return { value: true };
    },
  };
  const plugin = new Proxy(
    {},
    {
      get: (_target, name: string) =>
        methods[name] ?? (() => Promise.reject(new Error(`"${name}()" is not implemented`))),
    },
  );
  return { SecureStoragePlugin: plugin };
});

const SERVER = "https://journal.example.com/api/v1";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

async function load() {
  vi.resetModules();
  vi.stubEnv("VITE_API_URL", "https://journal.example.com/");
  const client = await import("@/shared/api/client");
  const platform = await import("@/platform");
  return { ...client, ...platform };
}

describe("the app's API client", () => {
  beforeEach(() => keystore.clear());
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("calls the configured server with the Bearer token and no cookies", async () => {
    const { api, tokens } = await load();
    const fetchMock = vi.fn(async () => json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await tokens.save({
      access: "A1",
      access_expires_in: 600,
      refresh: "R1",
      refresh_expires_at: "",
    });
    await api("/me");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${SERVER}/me`);
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer A1");
    expect((init.headers as Record<string, string>)["X-CSRFToken"]).toBeUndefined();
    // The refresh token is in the Keystore, never in localStorage.
    expect(keystore.get("journal.refresh")).toBe("R1");
    // eslint-disable-next-line no-restricted-properties -- the test proves nothing lands there
    expect(window.localStorage.length).toBe(0);
  });

  it("refreshes once for parallel 401s and repeats the requests", async () => {
    const { api, tokens } = await load();
    await tokens.save({
      access: "old",
      access_expires_in: 600,
      refresh: "R1",
      refresh_expires_at: "",
    });
    let refreshes = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init: RequestInit) => {
        if (url.endsWith("/auth/token/refresh")) {
          refreshes += 1;
          expect(JSON.parse(String(init.body))).toEqual({ refresh: "R1" });
          return json(200, {
            access: "new",
            access_expires_in: 600,
            refresh: "R2",
            refresh_expires_at: "",
          });
        }
        const auth = (init.headers as Record<string, string>).Authorization;
        return auth === "Bearer new"
          ? json(200, { ok: url })
          : json(401, { detail: "not_authenticated" });
      }),
    );
    const [a, b] = await Promise.all([api("/me"), api("/student/home")]);
    expect(a).toEqual({ ok: `${SERVER}/me` });
    expect(b).toEqual({ ok: `${SERVER}/student/home` });
    expect(refreshes).toBe(1);
    expect(keystore.get("journal.refresh")).toBe("R2");
  });

  it("forgets the tokens when the refresh is refused", async () => {
    const { api, isApiError, tokens } = await load();
    await tokens.save({
      access: "old",
      access_expires_in: 600,
      refresh: "R1",
      refresh_expires_at: "",
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/auth/token/refresh")
          ? json(401, { detail: "invalid_token" })
          : json(401, { detail: "not_authenticated" }),
      ),
    );
    const error = await api("/me").catch((e: unknown) => e);
    expect(isApiError(error, 401)).toBe(true);
    expect(keystore.has("journal.refresh")).toBe(false);
    expect(tokens.access()).toBeNull();
  });

  it("logs in with the token endpoints and keeps the 2FA ticket in memory", async () => {
    const { tokens } = await load();
    const { useLogin } = await import("@/features/auth/api");
    expect(useLogin).toBeTypeOf("function");
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        return json(200, {
          step: "done",
          access: "A",
          access_expires_in: 600,
          refresh: "R",
          refresh_expires_at: "",
        });
      }),
    );
    // The login request never carries a token and never triggers a refresh.
    const { api } = await import("@/shared/api/client");
    await api("/auth/token", { method: "POST", body: { login: "x", password: "y" } });
    expect(calls).toEqual([`${SERVER}/auth/token`]);
    expect(tokens.access()).toBeNull();
  });
});
