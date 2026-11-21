import { Link } from "react-router";

import { t } from "@/shared/i18n";

import styles from "./NotFoundPage.module.css";

export function NotFoundPage() {
  return (
    <main className={styles.column}>
      <p className={`mono ${styles.date}`}>404</p>
      <h1>{t("notFound.title")}</h1>
      <p>
        <Link to="/">{t("notFound.back")}</Link>
      </p>
    </main>
  );
}
