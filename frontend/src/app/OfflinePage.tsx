import { t } from "@/shared/i18n";
import { Button } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";

import styles from "./NotFoundPage.module.css";

/** «Нет соединения»: data is never cached, so offline there is only this. */
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
