import type { ReactNode } from "react";

import styles from "./EmptyState.module.css";

/** One line of text and an action. No illustrations. */
export function EmptyState({ text, action }: { text: string; action?: ReactNode }) {
  return (
    <p className={styles.empty}>
      {text}
      {action && <> {action}</>}
    </p>
  );
}
