import { useId } from "react";

import { t } from "@/shared/i18n";
import type { ThemePreference } from "@/shared/lib/theme";

import styles from "./ThemeSwitch.module.css";

const OPTIONS: ThemePreference[] = ["light", "dark", "system"];

type ThemeSwitchProps = { value: ThemePreference; onChange: (value: ThemePreference) => void };

export function ThemeSwitch({ value, onChange }: ThemeSwitchProps) {
  const name = useId();
  return (
    <fieldset className={styles.switch}>
      <legend className={styles.legend}>{t("theme.label")}</legend>
      {OPTIONS.map((option) => (
        <label key={option} className={styles.option}>
          <input
            type="radio"
            name={name}
            value={option}
            checked={value === option}
            onChange={() => onChange(option)}
          />
          <span>{t(`theme.${option}`)}</span>
        </label>
      ))}
    </fieldset>
  );
}
