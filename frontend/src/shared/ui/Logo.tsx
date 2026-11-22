import { t } from "@/shared/i18n";

import styles from "./Logo.module.css";

/**
 * Daftar — «тетрадь, журнал» in Uzbek and Tajik: the name of the program, not of the center.
 * The mark is a journal page: a margin line, three ruled lines and a red bookmark. Colours come
 * from the tokens, so it follows the theme; the PNG icons repeat it (mobile/scripts/make_icons.py).
 */
export function Logo({
  size = "md",
  tagline = false,
  className,
}: {
  size?: "md" | "lg";
  /** «электронный журнал» under the name — on the login panel. */
  tagline?: boolean;
  className?: string;
}) {
  return (
    <span className={[styles.logo, styles[size], className].filter(Boolean).join(" ")}>
      <svg className={styles.mark} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <rect className={styles.page} x="5.5" y="3.5" width="21" height="25" rx="3" />
        <line className={styles.margin} x1="11" y1="4" x2="11" y2="28" />
        <line className={styles.rule} x1="14" y1="13" x2="23" y2="13" />
        <line className={styles.rule} x1="14" y1="18" x2="23" y2="18" />
        <line className={styles.rule} x1="14" y1="23" x2="20" y2="23" />
        <path className={styles.bookmark} d="M19.5 3.5h4.5v8.5l-2.25-1.8-2.25 1.8z" />
      </svg>
      <span className={styles.words}>
        <span className={styles.name}>{t("app.productName")}</span>
        {tagline && <span className={styles.tagline}>{t("app.tagline")}</span>}
      </span>
    </span>
  );
}
