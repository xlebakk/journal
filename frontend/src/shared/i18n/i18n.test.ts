import { t } from ".";
import ru from "./ru.json";
import uz from "./uz.json";

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

describe("the Uzbek dictionary", () => {
  const russian = flatten(ru);
  const uzbek = flatten(uz);

  it("has exactly the keys of the Russian one", () => {
    expect(Object.keys(uzbek).sort()).toEqual(Object.keys(russian).sort());
  });

  it("keeps every placeholder", () => {
    const broken = Object.keys(russian).filter(
      (key) =>
        JSON.stringify(placeholders(russian[key]!)) !==
        JSON.stringify(placeholders(uzbek[key] ?? "")),
    );
    expect(broken).toEqual([]);
  });

  it("uses the letters oʻ and gʻ, not an ASCII apostrophe", () => {
    expect(Object.entries(uzbek).filter(([, text]) => text.includes("'"))).toEqual([]);
  });
});
