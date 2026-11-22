import { useRef } from "react";

import { useWeekParam } from "@/features/schedule/api";
import { errorMessage } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
import { formatDayLong, hhmm, startOfWeek, weekDays } from "@/shared/lib/week";
import { lessonMarks, RuledSkeleton, WeekNav } from "@/shared/ui";

import { useDiary, type DiaryLesson } from "./api";
import styles from "./Student.module.css";

const MARK: Record<string, MessageKey> = {
  late: "attendance.lateShort",
  absent: "attendance.absentShort",
  excused: "attendance.excusedShort",
};

function markOf(status: string): string {
  const key = MARK[status];
  return key ? t(key) : "";
}
const MIN_ROWS = 3;

function DayPage({ day, lessons, today }: { day: string; lessons: DiaryLesson[]; today: string }) {
  const empty = Math.max(0, MIN_ROWS - lessons.length);
  return (
    <section className={styles.day} aria-label={formatDayLong(day)}>
      <h2 className={day === today ? `${styles.dayHead} ${styles.today}` : styles.dayHead}>
        {formatDayLong(day)}
      </h2>
      <table className={styles.diaryTable}>
        <thead className="visually-hidden">
          <tr>
            <th scope="col">{t("student.subject")}</th>
            <th scope="col">{t("student.topic")}</th>
            <th scope="col">{t("student.grade")}</th>
          </tr>
        </thead>
        <tbody>
          {lessons.map((lesson) => {
            const cancelled = lesson.status === "cancelled";
            return (
              <tr key={lesson.id}>
                <td className={styles.colSubject}>
                  <span className={styles.time}>{hhmm(lesson.start_time)}</span>{" "}
                  <span className={cancelled ? styles.cancelled : undefined}>
                    {lesson.subject_name}
                  </span>
                  {lesson.lesson_type_short && (
                    <span className={styles.meta}> · {lesson.lesson_type_short}</span>
                  )}
                  {lessonMarks(lesson).map((mark) => (
                    <span key={mark.text} className={`${styles[mark.tone]} ${styles.meta}`}>
                      <br />
                      {mark.text}
                    </span>
                  ))}
                </td>
                <td>
                  {lesson.topic && <div>{lesson.topic}</div>}
                  {lesson.homework && (
                    <div className={styles.meta}>
                      {t("student.homework")}: {lesson.homework}
                    </div>
                  )}
                </td>
                <td className={styles.colMark}>
                  {lesson.attendance && markOf(lesson.attendance) && (
                    <span className={lesson.attendance === "absent" ? styles.red : styles.pencil}>
                      {markOf(lesson.attendance)}{" "}
                    </span>
                  )}
                  {lesson.grades.map((grade) => (
                    <span
                      key={grade.id}
                      className={grade.low ? styles.low : undefined}
                      title={`${grade.work_type_name}${grade.comment ? ` · ${grade.comment}` : ""}`}
                    >
                      {grade.value}{" "}
                    </span>
                  ))}
                </td>
              </tr>
            );
          })}
          {Array.from({ length: empty }, (_, i) => (
            <tr key={`empty-${i}`} className={styles.emptyRow} aria-hidden="true">
              <td className={styles.colSubject} />
              <td />
              <td className={styles.colMark} />
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/** «Дневник»: the week as a paper diary spread; arrows or a swipe turn the page (SPEC §6.2). */
export function DiaryPage() {
  const [monday, setMonday, today] = useWeekParam();
  const diary = useDiary(monday);
  const touch = useRef<number | null>(null);
  const days = weekDays(monday);
  const lessons = diary.data?.lessons ?? [];
  const byDay = (day: string) => lessons.filter((l) => l.date === day);
  const sunday = days[6]!;
  const left = days.slice(0, 3);
  const right = [...days.slice(3, 6), ...(byDay(sunday).length ? [sunday] : [])];

  const turn = (weeks: number) => {
    const date = new Date(`${monday}T00:00:00Z`);
    date.setUTCDate(date.getUTCDate() + weeks * 7);
    setMonday(date.toISOString().slice(0, 10));
  };

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("student.diary")}</h1>
        <WeekNav
          monday={monday}
          onChange={setMonday}
          onToday={() => setMonday(startOfWeek(today))}
        />
      </div>
      {diary.isPending ? (
        <RuledSkeleton rows={10} />
      ) : diary.error ? (
        <p className={styles.error}>{errorMessage(diary.error)}</p>
      ) : (
        <div
          className={styles.spread}
          onPointerDown={(e) => {
            if (e.pointerType !== "mouse") touch.current = e.clientX;
          }}
          onPointerUp={(e) => {
            if (touch.current === null) return;
            const dx = e.clientX - touch.current;
            touch.current = null;
            if (Math.abs(dx) > 60) turn(dx < 0 ? 1 : -1);
          }}
        >
          {[left, right].map((leaf, i) => (
            <div key={i} className={styles.leaf}>
              {leaf.map((day) => (
                <DayPage key={day} day={day} lessons={byDay(day)} today={today} />
              ))}
            </div>
          ))}
        </div>
      )}
      <p className={styles.meta}>{t("student.swipeHint")}</p>
    </section>
  );
}
