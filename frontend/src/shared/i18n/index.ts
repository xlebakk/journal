import ru from "./ru.json";

type Dictionary = typeof ru;

type Paths<T, Prefix extends string = ""> = {
  [K in keyof T & string]: T[K] extends string ? `${Prefix}${K}` : Paths<T[K], `${Prefix}${K}.`>;
}[keyof T & string];

export type MessageKey = Paths<Dictionary>;

// One language today; the second one plugs in here (SPEC §1, principle 6).
const messages: Dictionary = ru;

export function t(key: MessageKey, params?: Record<string, string | number>): string {
  let node: unknown = messages;
  for (const part of key.split(".")) {
    node = (node as Record<string, unknown>)[part];
  }
  if (typeof node !== "string") return key;
  if (!params) return node;
  return node.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

/** For keys built at runtime (server error codes): undefined if there is no translation. */
export function tMaybe(key: string, params?: Record<string, string | number>): string | undefined {
  const text = t(key as MessageKey, params);
  return text === key ? undefined : text;
}
