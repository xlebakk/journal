import { Link } from "react-router";

import { useTeacherToday, type Today } from "@/features/journal/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, Table } from "@/shared/ui";

const STATE: Record<string, MessageKey> = {
  upcoming: "today.upcoming",
  to_fill: "today.toFill",
  filled: "today.filled",
  cancelled: "today.cancelled",
};

type Row = Today["lessons"][number];

function LessonRows({ rows, withDate }: { rows: Row[]; withDate?: boolean }) {
  return (
    <Table>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td className="mono">
              {withDate && <>{formatDayLong(row.date)}, </>}
              {hhmm(row.start_time)}–{hhmm(row.end_time)}
            </td>
            <td>
              <Link to={`/teacher/journal/lessons/${row.id}`}>
                {row.group_name} · {row.subject_name}
              </Link>
              {row.is_substituted && (
                <span className={styles.status}> · {t("today.substitution")}</span>
              )}
            </td>
            <td>{row.room_name ?? "—"}</td>
            <td className={row.state === "to_fill" ? styles.error : undefined}>
              {t(STATE[row.state] ?? "today.upcoming")}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** «Сегодня» — the teacher's home (SPEC §7.1). */
export function TodayPage() {
  const today = useTeacherToday();
  if (today.isPending) return <RuledSkeleton rows={6} />;
  if (today.error || !today.data)
    return <p className={styles.error}>{errorMessage(today.error)}</p>;
  const data = today.data;
  return (
    <section className={styles.page}>
      <h1>{formatDayLong(data.today)}</h1>

      <section className={styles.section} aria-labelledby="today-lessons">
        <h2 id="today-lessons">{t("today.lessons")}</h2>
        {data.lessons.length ? (
          <LessonRows rows={data.lessons} />
        ) : (
          <EmptyState text={t("today.noLessons")} />
        )}
      </section>

      <section className={styles.section} aria-labelledby="today-unfilled">
        <h2 id="today-unfilled">{t("today.unfilled")}</h2>
        {data.unfilled.length ? (
          <LessonRows rows={data.unfilled} withDate />
        ) : (
          <EmptyState text={t("today.unfilledEmpty")} />
        )}
      </section>

      <section className={styles.section} aria-labelledby="today-attention">
        <h2 id="today-attention">{t("today.attention")}</h2>
        {data.attention.length ? (
          <Table>
            <tbody>
              {data.attention.map((row) => (
                <tr key={`${row.student}:${row.course}`}>
                  <td>{row.student_name}</td>
                  <td>
                    <Link to={`/teacher/journal?course=${row.course}`}>
                      {row.group_name} · {row.subject_name}
                    </Link>
                  </td>
                  <td className={styles.error}>
                    {row.reason === "attendance"
                      ? t("today.lowAttendance", {
                          percent: Math.round(Number(row.attendance_percent)),
                        })
                      : t("today.lowGrades", { grades: row.grades.join(", ") })}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState text={t("today.attentionEmpty")} />
        )}
      </section>
    </section>
  );
}
