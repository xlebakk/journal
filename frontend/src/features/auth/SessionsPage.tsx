import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { describeUserAgent } from "@/shared/lib/userAgent";
import { formatDateTime as when } from "@/shared/lib/time";
import { Button, EmptyState, RuledSkeleton, Table } from "@/shared/ui";

import { logout, useEndOtherSessions, useEndSession, useSessions, type Session } from "./api";
import styles from "./AccountPages.module.css";

export function SessionsTable({
  sessions,
  onEnd,
  busy,
}: {
  sessions: Session[];
  onEnd: (session: Session) => void;
  busy?: boolean;
}) {
  return (
    <Table>
      <thead>
        <tr>
          <th scope="col">{t("sessions.title")}</th>
          <th scope="col">{t("sessions.lastSeen")}</th>
          <th scope="col">{t("sessions.started")}</th>
          <th scope="col">
            <span className="visually-hidden">{t("sessions.end")}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {sessions.map((session) => (
          <tr key={session.id}>
            <td>
              {describeUserAgent(session.user_agent) || t("sessions.unknownDevice")}
              <span className={styles.meta}>
                {" "}
                <span className="mono">{session.ip ?? ""}</span>
                {session.current && <> · {t("sessions.current")}</>}
                {session.remember && <> · {t("sessions.remembered")}</>}
              </span>
            </td>
            <td className="mono">{when(session.last_seen_at)}</td>
            <td className="mono">{when(session.created_at)}</td>
            <td>
              <Button variant="danger" disabled={busy} onClick={() => onEnd(session)}>
                {t("sessions.end")}
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

export function SessionsPage() {
  const sessions = useSessions();
  const end = useEndSession();
  const endOthers = useEndOtherSessions();

  const onEnd = async (session: Session) => {
    if (session.current) {
      await logout();
      return;
    }
    await end.mutateAsync(session.id);
  };

  return (
    <section className={styles.page}>
      <h1>{t("sessions.title")}</h1>
      {sessions.isPending ? (
        <RuledSkeleton rows={3} />
      ) : sessions.error ? (
        <p className={styles.error}>{errorMessage(sessions.error)}</p>
      ) : (
        <>
          <SessionsTable sessions={sessions.data} onEnd={onEnd} busy={end.isPending} />
          {sessions.data.length > 1 ? (
            <div className={styles.actions}>
              <Button onClick={() => endOthers.mutate()} disabled={endOthers.isPending}>
                {t("sessions.endOthers")}
              </Button>
            </div>
          ) : (
            <EmptyState text={t("sessions.empty")} />
          )}
        </>
      )}
    </section>
  );
}
