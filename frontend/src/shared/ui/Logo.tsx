import { t } from "@/shared/i18n";

import styles from "./Logo.module.css";

/**
 * Daftar — «тетрадь, журнал» in Tajik: the name of the program, not of the center.
 * The mark is a closed exercise book drawn in one line — the cover, the pages under it — with a
 * red bookmark (stage 19, after the customer's login mock-up). The line takes the text colour,
 * so the same mark works on the white header and on the night of the login page.
 */
export function Logo({
  size = "md",
  tagline = false,
  tone = "day",
  className,
}: {
  size?: "md" | "lg";
  /** «Электронный журнал» under the name — on the login panel. */
  tagline?: boolean;
  /** "night": white line and text, for the dark login panel. */
  tone?: "day" | "night";
  className?: string;
}) {
  return (
    <span
      className={[styles.logo, styles[size], tone === "night" && styles.night, className]
        .filter(Boolean)
        .join(" ")}
    >
      <svg className={styles.mark} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <path
          className={styles.line}
          d="M9 7.5C7 7.5 5.75 8.75 5.75 10.75v15C5.75 27.4 7.1 28.5 8.75 28.5H23"
        />
        <rect className={styles.cover} x="9" y="3.5" width="17.25" height="21.5" rx="2.5" />
        <path className={styles.line} d="M12.25 4v20.5" />
        <path className={styles.bookmark} d="M19.25 3.5h4.25v9.25l-2.125-1.7-2.125 1.7z" />
      </svg>
      <span className={styles.words}>
        <span className={styles.name}>{t("app.productName")}</span>
        {tagline && <span className={styles.tagline}>{t("app.tagline")}</span>}
      </span>
    </span>
  );
}
