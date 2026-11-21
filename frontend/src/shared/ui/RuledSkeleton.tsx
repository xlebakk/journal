import { t } from "@/shared/i18n";

import styles from "./RuledSkeleton.module.css";

/** Loading state: empty ruled lines instead of a spinner. */
export function RuledSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className={styles.skeleton} role="status" aria-label={t("common.loading")}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={styles.row} />
      ))}
    </div>
  );
}
