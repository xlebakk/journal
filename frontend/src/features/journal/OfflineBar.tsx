import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button } from "@/shared/ui";

import styles from "./Journal.module.css";
import { flush, queueSnapshot, resolve, useQueue } from "./offlineQueue";
import { useOnline } from "./useOnline";

const RETRY_MS = 15_000;

/** Sends the queue when the network comes back, retries now and then, guards the tab. */
function useSync() {
  const queryClient = useQueryClient();
  useEffect(() => {
    const send = () => void flush(queryClient);
    const timer = setInterval(() => {
      if (navigator.onLine && queueSnapshot().pending.length > 0) send();
    }, RETRY_MS);
    // Unsent changes live only in this tab: closing it loses them, so ask first.
    const guard = (event: BeforeUnloadEvent) => {
      if (queueSnapshot().pending.length === 0) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("online", send);
    window.addEventListener("beforeunload", guard);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", send);
      window.removeEventListener("beforeunload", guard);
    };
  }, [queryClient]);
}

/** «Нет сети · не отправлено: 3», conflicts to decide; nothing when all is sent (stage 13). */
export function OfflineBar() {
  useSync();
  const queryClient = useQueryClient();
  const online = useOnline();
  const { pending, problems, syncing } = useQueue();
  if (online && pending.length === 0 && problems.length === 0) return null;
  return (
    <section className={styles.offlineBar} aria-live="polite" aria-label={t("offline.barTitle")}>
      {!online && <p className={styles.offlineLine}>{t("offline.barOffline")}</p>}
      {pending.length > 0 && (
        <div className={styles.offlineLine}>
          <span>
            {t(syncing ? "offline.barSyncing" : "offline.barPending", { count: pending.length })}
          </span>
          <span className={styles.offlineLabels}>{pending.map((p) => p.label).join(" · ")}</span>
          {online && !syncing && (
            <Button onClick={() => void flush(queryClient)}>{t("offline.sendNow")}</Button>
          )}
        </div>
      )}
      {problems.map((problem) => (
        <div key={problem.item.id} className={styles.offlineLine} role="alert">
          <span className={styles.error}>
            {problem.kind === "conflict"
              ? t("offline.conflict", { label: problem.item.label })
              : t("offline.refused", {
                  label: problem.item.label,
                  error: errorMessage(problem.error),
                })}
          </span>
          {problem.kind === "conflict" && problem.item.force && (
            <Button onClick={() => void resolve(problem, true, queryClient)}>
              {t("offline.keepMine")}
            </Button>
          )}
          <Button onClick={() => void resolve(problem, false, queryClient)}>
            {problem.kind === "conflict" ? t("offline.takeServer") : t("offline.dismiss")}
          </Button>
        </div>
      ))}
    </section>
  );
}
