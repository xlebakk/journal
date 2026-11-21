import { t } from "@/shared/i18n";
import { Button, EmptyState } from "@/shared/ui";

import styles from "./NotFoundPage.module.css";

/** «Нет соединения» (SPEC §13): data is never cached, so offline there is only this. */
export function OfflinePage({ onRetry }: { onRetry: () => void }) {
  return (
    <main className={styles.column}>
      <h1>{t("offline.title")}</h1>
      <EmptyState
        text={t("offline.text")}
        action={<Button onClick={onRetry}>{t("offline.retry")}</Button>}
      />
    </main>
  );
}
