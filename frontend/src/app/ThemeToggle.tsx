import { Moon, Sun } from "lucide-react";

import { t } from "@/shared/i18n";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { useTheme } from "@/shared/lib/theme";

import styles from "./AppShell.module.css";

/**
 * Stage 19: light or dark in one press, right in the header. Before the first press the page
 * follows the system; the press fixes the other theme on this device.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const dark = theme === "dark" || (theme === "system" && systemDark);
  const label = dark ? t("theme.toLight") : t("theme.toDark");
  return (
    <button
      type="button"
      className={styles.themeToggle}
      aria-label={label}
      title={label}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {dark ? (
        <Sun size={19} strokeWidth={1.75} aria-hidden="true" />
      ) : (
        <Moon size={19} strokeWidth={1.75} aria-hidden="true" />
      )}
    </button>
  );
}
