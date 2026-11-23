import ru from "./ru.json";

type Dictionary = typeof ru;

type Paths<T, Prefix extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${Prefix}${K}` : Paths<T[K], `${Prefix}${K}.`>;
}[keyof T & string];

export type MessageKey = Paths<Dictionary>;

/**
 * Russian is the center's language and ships in the main bundle; Tajik and English load lazily
 * (stage 19; Uzbek was dropped at the customer's request).
 */
export type Language = "ru" | "tg" | "en";
export const LANGUAGES: readonly Language[] = ["ru", "tg", "en"];

const LOADERS: Record<Exclude<Language, "ru">, () => Promise<{ default: unknown }>> = {
  tg: () => import("./tg.json"),
  en: () => import("./en.json"),
};

const STORAGE_KEY = "journal.language";

let current: Language = "ru";
let messages: Dictionary = ru;

function lookup(dictionary: unknown, key: string): string | undefined {
  let node = dictionary;
  for (const part of key.split(".")) {
    node = (node as Record<string, unknown> | undefined)?.[part];
  }
  return typeof node === "string" ? node : undefined;
}

export function t(key: MessageKey, params?: Record<string, string | number>): string {
  // A string missing from the second language falls back to Russian, then to the key.
  const text = lookup(messages, key) ?? lookup(ru, key);
  if (text === undefined) return key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** For keys built at runtime (server error codes): undefined if there is no translation. */
export function tMaybe(key: string, params?: Record<string, string | number>): string | undefined {
  const text = t(key as MessageKey, params);
  return text === key ? undefined : text;
}

function storedLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return LANGUAGES.find((option) => option === stored) ?? "ru";
  } catch {
    return "ru";
  }
}

/** Runs before the first render, so even module-level `t()` calls of lazy pages are right. */
export async function initLanguage(): Promise<void> {
  const wanted = storedLanguage();
  if (wanted !== "ru") {
    try {
      messages = (await LOADERS[wanted]()).default as Dictionary;
      current = wanted;
    } catch {
      // The chunk did not load (no network on a cold start): stay with Russian.
    }
  }
  document.documentElement.lang = current;
}

export function language(): Language {
  return current;
}

/** «январь,февраль,…» → a list; for names Intl may not know (Tajik in most engines). */
export function names(key: "dates.months" | "dates.weekdays" | "dates.weekdaysShort"): string[] {
  return t(key).split(",");
}

/** The choice is per device (like the theme); the page reloads in the new language. */
export function setLanguage(next: Language): void {
  if (next === current) return;
  try {
    localStorage.setItem(STORAGE_KEY, next);
  } catch {
    return;
  }
  window.location.reload();
}
