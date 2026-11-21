import { ChevronLeft, ChevronRight } from "lucide-react";
import { useSearchParams } from "react-router";

import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday, isoWeekday, WEEKDAY_NAMES } from "@/shared/lib/week";
import { Button, RuledSkeleton, Table } from "@/shared/ui";

import { useStudentAttendance, type StudentAttendance } from "./api";
import styles from "./Student.module.css";

const MARK: Record<string, string> = { late: "оп", absent: "н", excused: "у" };

function monthName(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("ru-RU", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y ?? 2026, (m ?? 1) - 1, 1)));
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const date = new Date(Date.UTC(y ?? 2026, (m ?? 1) - 1 + delta, 1));
  return date.toISOString().slice(0, 7);
}

function percent(value: string | null): string {
  return value === null ? "—" : `${Math.round(Number(value))}%`;
}

function Calendar({ data, today }: { data: StudentAttendance; today: string }) {
  const first = data.days[0]?.date;
  const blanks = first ? isoWeekday(first) - 1 : 0;
  return (
    <div className={styles.calendar} role="grid" aria-label={monthName(data.month)}>
      <div role="row" className="visually-hidden">
        {WEEKDAY_NAMES.map((name) => (
          <span key={name} role="columnheader">
            {name}
          </span>
        ))}
      </div>
      {WEEKDAY_NAMES.map((name) => (
        <span key={name} className={styles.weekday} aria-hidden="true">
          {name.slice(0, 2)}
        </span>
      ))}
      {Array.from({ length: blanks }, (_, i) => (
        <span
          key={`blank-${i}`}
          className={`${styles.calendarDay} ${styles.blank}`}
          aria-hidden="true"
        />
      ))}
      {data.days.map((day) => (
        <div
          key={day.date}
          role="gridcell"
          className={[
            styles.calendarDay,
            day.lessons > 0 && styles.hasLessons,
            day.date === today && styles.today,
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span className={styles.dayNumber}>{Number(day.date.slice(8, 10))}</span>
          {day.marks.length > 0 && (
            <ul className={styles.dayMarks}>
              {day.marks.map((mark, i) => (
                <li
                  key={i}
                  className={mark.status === "absent" ? styles.red : styles.pencil}
                  title={mark.subject_name}
                >
                  {MARK[mark.status] ?? ""} {mark.subject_short}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}

/** «Посещаемость»: per subject and overall; a month calendar of absences and lates (SPEC §6.5). */
export function AttendancePage() {
  const [params, setParams] = useSearchParams();
  const month = params.get("month") || undefined;
  const attendance = useStudentAttendance(month);
  const data = attendance.data;
  const today = centerToday();

  if (attendance.isPending) return <RuledSkeleton rows={8} />;
  if (attendance.error || !data)
    return <p className={styles.error}>{errorMessage(attendance.error)}</p>;
  const low = (value: string | null) => value !== null && Number(value) < data.threshold;

  return (
    <section className={styles.page}>
      <h1>{t("student.attendanceTitle")}</h1>
      <Table>
        <thead>
          <tr>
            <th scope="col">{t("student.subject")}</th>
            <th scope="col" className={styles.number}>
              %
            </th>
            <th scope="col" className={styles.number}>
              {t("student.present")}
            </th>
            <th scope="col" className={styles.number}>
              {t("student.late")}
            </th>
            <th scope="col" className={styles.number}>
              {t("student.absent")}
            </th>
            <th scope="col" className={styles.number}>
              {t("student.excused")}
            </th>
          </tr>
        </thead>
        <tbody>
          {data.courses.map((row) => (
            <tr key={row.course}>
              <td>{row.subject_name}</td>
              <td className={`${styles.number} ${low(row.percent) ? styles.low : ""}`}>
                {percent(row.percent)}
              </td>
              <td className={styles.number}>{row.present}</td>
              <td className={styles.number}>{row.late}</td>
              <td className={styles.number}>{row.absent}</td>
              <td className={styles.number}>{row.excused}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">{t("student.overall")}</th>
            <td className={`${styles.number} ${low(data.overall) ? styles.low : ""}`}>
              {percent(data.overall)}
            </td>
            <td colSpan={4} />
          </tr>
        </tbody>
      </Table>
      {data.excused > 0 && (
        <p className={styles.meta}>{t("student.excusedSeparately", { count: data.excused })}</p>
      )}

      <div className={styles.titleRow}>
        <h2>{t("student.calendar")}</h2>
        <div className={styles.monthNav}>
          <Button
            aria-label={t("student.previousMonth")}
            onClick={() => setParams({ month: shiftMonth(data.month, -1) }, { replace: true })}
          >
            <ChevronLeft size={18} strokeWidth={1.5} aria-hidden="true" />
          </Button>
          <span className={styles.monthName}>{monthName(data.month)}</span>
          <Button
            aria-label={t("student.nextMonth")}
            onClick={() => setParams({ month: shiftMonth(data.month, 1) }, { replace: true })}
          >
            <ChevronRight size={18} strokeWidth={1.5} aria-hidden="true" />
          </Button>
        </div>
      </div>
      <Calendar data={data} today={today} />
    </section>
  );
}
