import { useId } from "react";

import { language, LANGUAGES, setLanguage, t } from "@/shared/i18n";

// The same segmented control as the theme switch.
import styles from "./ThemeSwitch.module.css";

/** «Русский | Тоҷикӣ | English»: each name in its own language; the page reloads on change. */
export function LanguageSwitch({ className }: { className?: string }) {
  const name = useId();
  const current = language();
  return (
    <fieldset className={[styles.switch, className].filter(Boolean).join(" ")}>
      <legend className={styles.legend}>{t("language.label")}</legend>
      {LANGUAGES.map((option) => (
        <label key={option} className={styles.option} lang={option}>
          <input
            type="radio"
            name={name}
            value={option}
            checked={current === option}
            onChange={() => setLanguage(option)}
          />
          <span>{t(`language.${option}`)}</span>
        </label>
      ))}
    </fieldset>
  );
}
