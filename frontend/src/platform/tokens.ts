/**
 * Tokens of the Android app (SPEC §11): the access token only in memory, the refresh token
 * only in the Android Keystore (secure storage plugin). Never in localStorage. In a browser
 * none of this is used: the site works with the session cookie.
 */
import { Capacitor } from "@capacitor/core";

const REFRESH_KEY = "journal.refresh";

export type TokenPair = {
  access: string;
  access_expires_in: number;
  refresh: string;
  refresh_expires_at: string;
};

type SecureStorage = {
  get(options: { key: string }): Promise<{ value: string }>;
  set(options: { key: string; value: string }): Promise<{ value: boolean }>;
  remove(options: { key: string }): Promise<{ value: boolean }>;
};

let access: string | null = null;
let pending: Promise<boolean> | null = null;
// The module, not the plugin: a Capacitor plugin is a Proxy that answers every property,
// `then` included, so a promise resolved with it would wait for a «then» that never comes.
let storage: Promise<{ SecureStoragePlugin: SecureStorage }> | null = null;
/** Where refresh requests go; set by the API client (keeps this module free of fetch URLs). */
let refreshUrl = "";

/** Resolves to the module; read `.SecureStoragePlugin` at the call site, never return it. */
function secure(): Promise<{ SecureStoragePlugin: SecureStorage }> {
  if (!Capacitor.isNativePlatform()) return Promise.reject(new Error("not_native"));
  storage ??= import("capacitor-secure-storage-plugin");
  return storage;
}

async function readRefresh(): Promise<string | null> {
  try {
    return (await (await secure()).SecureStoragePlugin.get({ key: REFRESH_KEY })).value || null;
  } catch {
    return null; // nothing stored yet
  }
}

async function doRefresh(): Promise<boolean> {
  const refresh = await readRefresh();
  if (!refresh) return false;
  let response: Response;
  try {
    response = await fetch(refreshUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh }),
      credentials: "omit",
    });
  } catch {
    return false; // offline: keep the refresh token for later
  }
  if (!response.ok) {
    // Spent, expired or revoked: this login is over.
    await tokens.clear();
    return false;
  }
  await tokens.save((await response.json()) as TokenPair);
  return true;
}

export const tokens = {
  configure(url: string) {
    refreshUrl = url;
  },

  access(): string | null {
    return access;
  },

  async save(pair: TokenPair): Promise<void> {
    access = pair.access;
    await (await secure()).SecureStoragePlugin.set({ key: REFRESH_KEY, value: pair.refresh });
  },

  async clear(): Promise<void> {
    access = null;
    try {
      await (await secure()).SecureStoragePlugin.remove({ key: REFRESH_KEY });
    } catch {
      // already empty
    }
  },

  /** One refresh at a time: parallel 401s wait for the same rotation (a token works once). */
  refresh(): Promise<boolean> {
    pending ??= doRefresh().finally(() => {
      pending = null;
    });
    return pending;
  },
};
