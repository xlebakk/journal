import { t } from ".";
import ru from "./ru.json";
import en from "./en.json";
import tg from "./tg.json";

function flatten(node: unknown, prefix = ""): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(node as Record<string, unknown>)) {
    if (typeof value === "string") out[prefix + key] = value;
    else Object.assign(out, flatten(value, `${prefix}${key}.`));
  }
  return out;
}

const placeholders = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe("t", () => {
  it("returns Russian strings by key", () => {
    expect(t("theme.dark")).toBe("тёмная");
  });

  it("substitutes parameters", () => {
    expect(t("stamp.menu", { name: "Фарход Алиев" })).toBe("Меню пользователя Фарход Алиев");
  });
});

describe.each([
  ["Tajik", tg],
  ["English", en],
])("the %s dictionary", (_, dictionary) => {
  const russian = flatten(ru);
  const other = flatten(dictionary);

  it("has exactly the keys of the Russian one", () => {
    expect(Object.keys(other).sort()).toEqual(Object.keys(russian).sort());
  });

  it("keeps every placeholder", () => {
    const broken = Object.keys(russian).filter(
      (key) =>
        JSON.stringify(placeholders(russian[key]!)) !==
        JSON.stringify(placeholders(other[key] ?? "")),
    );
    expect(broken).toEqual([]);
  });
});
