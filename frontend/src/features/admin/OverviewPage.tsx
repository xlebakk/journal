import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";

import styles from "@/features/schedule/SchedulePage.module.css";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDateTime } from "@/shared/lib/time";
import { formatDate, formatDayLong } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, Table } from "@/shared/ui";

import { actionText } from "./audit/labels";

type Overview = Schemas["Overview"];

/** «Обзор» (SPEC §8.1): every block leads to an action, not just a number. */
export function OverviewPage() {
  const overview = useQuery({
    queryKey: ["admin", "overview"],
    queryFn: () => api<Overview>("/admin/overview"),
    refetchInterval: 120_000,
  });
  if (overview.isPending) return <RuledSkeleton rows={8} />;
  if (overview.error || !overview.data) {
    return <p className={styles.error}>{errorMessage(overview.error)}</p>;
  }
  const data = overview.data;
  const lessons = data.lessons;
  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("nav.overview")}</h1>
        <span className={styles.status}>{formatDayLong(data.today)}</span>
      </div>

      <section className={styles.section} aria-labelledby="ov-today">
        <div className={styles.titleRow}>
          <h2 id="ov-today">{t("overview.today")}</h2>
          <Link to="/admin/schedule">{t("overview.openSchedule")}</Link>
        </div>
        <p className="mono">
          {lessons.total} {t("overview.total")} · {lessons.conducted} {t("overview.conducted")} ·{" "}
          <span className={lessons.to_fill ? styles.error : undefined}>
            {lessons.to_fill} {t("overview.toFill")}
          </span>
          {lessons.cancelled > 0 && (
            <>
              {" "}
              · {lessons.cancelled} {t("overview.cancelled")}
            </>
          )}
        </p>
      </section>

      <section className={styles.section} aria-labelledby="ov-unfilled">
        <h2 id="ov-unfilled">{t("overview.unfilled")}</h2>
        {data.unfilled.length === 0 ? (
          <EmptyState text={t("overview.noUnfilled")} />
        ) : (
          <Table>
            <tbody>
              {data.unfilled.map((teacher) => (
                <tr key={teacher.teacher}>
                  <th scope="row">
                    {teacher.teacher_name}
                    <span className={styles.status}>
                      {" "}
                      · {t("overview.lessons", { count: teacher.count })}
                    </span>
                  </th>
                  <td>
                    {teacher.lessons.map((lesson, i) => (
                      <span key={lesson.id}>
                        {i > 0 && ", "}
                        <Link to={`/admin/journal/lessons/${lesson.id}`}>
                          {formatDate(lesson.date)} {lesson.group_name} · {lesson.subject_name}
                        </Link>
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>

      <section className={styles.section} aria-labelledby="ov-attendance">
        <h2 id="ov-attendance">
          {t("overview.lowAttendance", {
            percent: data.attendance_threshold,
            days: data.attendance_window_days,
          })}
        </h2>
        {data.low_attendance.length === 0 ? (
          <EmptyState text={t("overview.noLowAttendance")} />
        ) : (
          <Table>
            <tbody>
              {data.low_attendance.map((row) => (
                <tr key={`${row.student}-${row.course}`}>
                  <th scope="row">
                    <Link to={`/admin/users/${row.student}`}>{row.full_name}</Link>
                  </th>
                  <td>
                    {row.group_name} · {row.subject_name}
                  </td>
                  <td className={`mono ${styles.error}`}>
                    {Math.round(Number(row.attendance_percent))}%
                  </td>
                  <td>
                    <Link to={`/admin/journal?course=${row.course}`}>
                      {t("overview.openJournal")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>

      <section className={styles.section} aria-labelledby="ov-blocked">
        <h2 id="ov-blocked">{t("overview.blocked")}</h2>
        <p className={styles.note}>
          {t("overview.failed", { count: data.failed_logins_24h })} ·{" "}
          <Link to="/admin/audit?tab=logins">{t("audit.tabLogins")}</Link>
        </p>
        {data.blocked_logins.length === 0 ? (
          <EmptyState text={t("overview.noBlocked")} />
        ) : (
          <Table>
            <tbody>
              {data.blocked_logins.map((row) => (
                <tr key={row.login}>
                  <th scope="row" className="mono">
                    {row.login}
                  </th>
                  <td>{t("overview.attempts", { count: row.attempts })}</td>
                  <td>{formatDateTime(row.last_at)}</td>
                  <td>
                    <Link to={`/admin/users?q=${encodeURIComponent(row.login)}`}>
                      {t("nav.users")}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>

      <section className={styles.section} aria-labelledby="ov-audit">
        <div className={styles.titleRow}>
          <h2 id="ov-audit">{t("overview.audit")}</h2>
          <Link to="/admin/audit">{t("overview.allAudit")}</Link>
        </div>
        <Table>
          <tbody>
            {data.audit.map((entry) => (
              <tr key={entry.id}>
                <td className="mono">{formatDateTime(entry.at)}</td>
                <td>{entry.actor_name ?? t("audit.system")}</td>
                <td>{actionText(entry.action)}</td>
                <td className={styles.status}>{entry.reason}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </section>
    </section>
  );
}
