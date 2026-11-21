import { t } from ".";

describe("t", () => {
  it("returns Russian strings by key", () => {
    expect(t("theme.dark")).toBe("тёмная");
  });

  it("substitutes parameters", () => {
    expect(t("stamp.menu", { name: "Фарход Алиев" })).toBe("Меню пользователя Фарход Алиев");
  });
});
