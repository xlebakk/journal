import { useCallback, useState } from "react";

import { readStorage, writeStorage } from "./storage";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "journal.theme";

export function readThemePreference(): ThemePreference {
  const stored = readStorage(STORAGE_KEY);
  return stored === "light" || stored === "dark" ? stored : "system";
}

/** "system" removes the attribute so tokens.css follows prefers-color-scheme. */
export function applyTheme(preference: ThemePreference): void {
  const root = document.documentElement;
  if (preference === "system") delete root.dataset.theme;
  else root.dataset.theme = preference;
}

export function useTheme(): [ThemePreference, (next: ThemePreference) => void] {
  const [preference, setPreference] = useState(readThemePreference);
  const update = useCallback((next: ThemePreference) => {
    applyTheme(next);
    writeStorage(STORAGE_KEY, next === "system" ? null : next);
    setPreference(next);
  }, []);
  return [preference, update];
}
