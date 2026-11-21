import { act, renderHook } from "@testing-library/react";

import { applyTheme, readThemePreference, useTheme } from "./theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("defaults to the system preference", () => {
    expect(readThemePreference()).toBe("system");
  });

  it("system removes the attribute so CSS follows prefers-color-scheme", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("remembers an explicit choice", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current[1]("light"));
    expect(result.current[0]).toBe("light");
    expect(readThemePreference()).toBe("light");
  });
});
