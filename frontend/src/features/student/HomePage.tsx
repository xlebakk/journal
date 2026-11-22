import { Link } from "react-router";

import { AnnouncementsBoard } from "@/features/announcements/AnnouncementsBoard";
import { DebtNotice } from "@/features/payments/MyPaymentsPage";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";
import { EmptyState, lessonMarks, RuledSkeleton, Table } from "@/shared/ui";

import { useStudentHome } from "./api";
import styles from "./Student.module.css";

/** «Главная» of a student: announcements, today, new grades, homework. */
export function HomePage() {
  const home = useStudentHome();
  if (home.isPending) return <RuledSkeleton rows={8} />;
  if (home.error || !home.data) return <p className={styles.error}>{errorMessage(home.error)}</p>;
  const data = home.data;

  return (
    <section className={styles.page}>
      <h1>{formatDayLong(data.today)}</h1>

      <DebtNotice />

      <AnnouncementsBoard className={styles.section} />

      <section className={styles.section} aria-labelledby="home-today">
        <h2 id="home-today">{t("student.today")}</h2>
        {data.lessons_today.length === 0 ? (
          <EmptyState text={t("student.noLessonsToday")} />
        ) : (
          <ul className={styles.list}>
            {data.lessons_today.map((lesson) => (
              <li key={lesson.id}>
                <span className={styles.time}>
                  {hhmm(lesson.start_time)}–{hhmm(lesson.end_time)}
                </span>
                <span className={lesson.status === "cancelled" ? styles.cancelled : undefined}>
                  {lesson.subject_name}
                </span>
                <span className={styles.meta}>
                  {lesson.room_name
                    ? t("schedule.room", { room: lesson.room_name })
                    : t("schedule.noRoom")}{" "}
                  · {lesson.teacher_name}
                </span>
                {lessonMarks(lesson).map((mark) => (
                  <span key={mark.text} className={styles[mark.tone]}>
                    {mark.text}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-labelledby="home-grades">
        <h2 id="home-grades">{t("student.newGrades")}</h2>
        {data.new_grades.length === 0 ? (
          <EmptyState text={t("student.noNewGrades")} />
        ) : (
          <ul className={styles.list}>
            {data.new_grades.map((grade) => (
              <li key={grade.id}>
                <span className={`${styles.grade} ${grade.low ? styles.low : ""}`}>
                  {grade.value}
                </span>
                <span>{grade.subject_name}</span>
                <span className={styles.meta}>
                  {formatDayLong(grade.date)} · {grade.work_type_name}
                  {grade.comment && <> · {grade.comment}</>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-labelledby="home-homework">
        <h2 id="home-homework">{t("student.homework")}</h2>
        {data.homework.length === 0 ? (
          <EmptyState text={t("student.noHomework")} />
        ) : (
          <ul className={styles.list}>
            {data.homework.map((item) => (
              <li key={item.lesson}>
                <span>{item.subject_name}</span>
                <span className={styles.meta}>
                  {item.due_on
                    ? t("student.dueOn", { date: formatDayLong(item.due_on) })
                    : t("student.assignedOn", { date: formatDayLong(item.assigned_on) })}
                  {item.topic && <> · {item.topic}</>}
                </span>
                <p className={styles.homework}>{item.homework}</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-labelledby="home-subjects">
        <div className={styles.titleRow}>
          <h2 id="home-subjects">
            {data.period_name
              ? t("student.subjectsPeriod", { period: data.period_name })
              : t("student.subjects")}
          </h2>
          <Link to="/student/attendance">{t("student.attendanceLink")}</Link>
        </div>
        {data.subjects.length === 0 ? (
          <EmptyState text={t("student.noSubjects")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("student.subject")}</th>
                <th scope="col" className={styles.number}>
                  {t("student.average")}
                </th>
                <th scope="col" className={styles.number}>
                  {t("student.attendance")}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.subjects.map((row) => (
                <tr key={row.course}>
                  <td>{row.subject_name}</td>
                  <td className={`${styles.number} ${row.low ? styles.low : ""}`}>
                    {row.average ?? "—"}
                  </td>
                  <td className={styles.number}>
                    {row.attendance_percent === null
                      ? "—"
                      : `${Math.round(Number(row.attendance_percent))}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </section>
    </section>
  );
}
