import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatTime } from "@/shared/lib/time";
import { Button } from "@/shared/ui";

import styles from "./Journal.module.css";
import type { SaveState } from "./useSave";

/** «Сохранено · 14:32» or «Не сохранено — повторить», plus «отменить» for 10 s (SPEC §7.2). */
export function SaveStatus({
  state,
  retry,
  undo,
}: {
  state: SaveState;
  retry: (() => void) | null;
  undo: (() => void) | null;
}) {
  return (
    <div className={styles.saveStatus} role="status" aria-live="polite">
      {state.kind === "saved" && <span>{t("journal.saved", { time: formatTime(state.at) })}</span>}
      {state.kind === "undone" && <span>{t("journal.undone")}</span>}
      {state.kind === "error" && (
        <span className={styles.error}>
          {t("journal.unsaved")}: {errorMessage(state.error)}{" "}
          {retry && <Button onClick={retry}>{t("journal.retry")}</Button>}
        </span>
      )}
      {undo && <Button onClick={undo}>{t("journal.undo")}</Button>}
    </div>
  );
}
