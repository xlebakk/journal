import { render, screen } from "@testing-library/react";

import { InitialsStamp } from "./InitialsStamp";
import { initialsOf, stampInk } from "./stamp";

describe("initialsOf", () => {
  it("takes first name then last name", () => {
    expect(initialsOf("Фарход", "Алиев")).toBe("ФА");
  });

  it("trims and uppercases", () => {
    expect(initialsOf("  мадина ", " каримова")).toBe("МК");
  });
});

describe("stampInk", () => {
  it("is stable and within 1..6", () => {
    const ids = Array.from({ length: 200 }, (_, i) => `00000000-0000-4000-8000-${i}`);
    for (const id of ids) {
      const ink = stampInk(id);
      expect(ink).toBe(stampInk(id));
      expect(ink).toBeGreaterThanOrEqual(1);
      expect(ink).toBeLessThanOrEqual(6);
    }
    expect(new Set(ids.map(stampInk)).size).toBe(6);
  });
});

describe("InitialsStamp", () => {
  it("renders an accessible button with initials", () => {
    render(<InitialsStamp userId="u1" firstName="Фарход" lastName="Алиев" />);
    const button = screen.getByRole("button", { name: "Меню пользователя Фарход Алиев" });
    expect(button).toHaveTextContent("ФА");
  });
});
