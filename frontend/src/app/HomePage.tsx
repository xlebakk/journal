import { Link } from "react-router";

import { t } from "@/shared/i18n";
import { formatJournalHeader } from "@/shared/lib/time";

import styles from "./HomePage.module.css";

/** Placeholder until stage 1 brings the login page. */
export function HomePage() {
  return (
    <main className={styles.column}>
      <p className={`mono ${styles.date}`}>{formatJournalHeader(new Date())}</p>
      <h1>{t("app.centerName")}</h1>
      <p className={styles.product}>{t("app.productName")}</p>
      <p>{t("home.stageNote")}</p>
      {import.meta.env.DEV && <Link to="/dev/styleguide">{t("home.styleguideLink")}</Link>}
    </main>
  );
}
