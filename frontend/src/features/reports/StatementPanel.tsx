import { useState } from "react";

import { useExamCourses } from "@/features/exams/api";
import { useTerms } from "@/features/journal/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, SelectField, Table, TextField } from "@/shared/ui";

import { num, useStatement, type Query } from "./api";
import { ExportButtons } from "./ExportButtons";

/** «Ведомость» of a course for a period: screen, print, XLSX / CSV. */
export function StatementPanel() {
  const courses = useExamCourses();
  const [picked, setPicked] = useState("");
  const course = picked || courses.data?.[0]?.id;
  const terms = useTerms(course);
  const [period, setPeriod] = useState("default");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const list = terms.data ?? [];
  let query: Query = {};
  if (period === "year" && list.length) {
    query = { from: list[0]?.starts_on, to: list[list.length - 1]?.ends_on };
  } else if (period === "custom") {
    query = { from: from || undefined, to: to || undefined };
  } else if (period !== "default") {
    query = { term: period };
  }
  const statement = useStatement(course, query);

  if (courses.isPending) return <RuledSkeleton rows={4} />;
  if (!courses.data?.length) return <EmptyState text={t("reports.noCourses")} />;
  const data = statement.data;
  return (
    <div className={styles.section}>
      <div className={`${styles.toolbar} ${styles.noPrint}`}>
        <SelectField
          label={t("reports.course")}
          value={course}
          onChange={(e) => {
            setPicked(e.target.value);
            setPeriod("default");
          }}
          options={courses.data.map((c) => ({
            value: c.id,
            label: `${c.group_name} · ${c.subject_name}`,
          }))}
        />
        <SelectField
          label={t("reports.period")}
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          options={[
            { value: "default", label: t("reports.term") },
            ...list.map((term) => ({ value: term.id, label: term.name })),
            { value: "year", label: t("reports.wholeYear") },
            { value: "custom", label: t("reports.custom") },
          ]}
        />
        {period === "custom" && (
          <>
            <TextField
              label={t("reports.from")}
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
            <TextField
              label={t("reports.to")}
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </>
        )}
      </div>
      {statement.error && <p className={styles.error}>{errorMessage(statement.error)}</p>}
      {data && (
        <>
          <div className={styles.titleRow}>
            <h2>
              {data.course.group_name} · {data.course.subject_name}
              <span className={styles.status}>
                {" "}
                · {data.course.teacher_name} ·{" "}
                {t("reports.periodLine", {
                  from: formatDate(data.first),
                  to: formatDate(data.last),
                })}
              </span>
            </h2>
            <ExportButtons path={`/reports/courses/${data.course.id}`} query={query} />
          </div>
          {data.rows.length === 0 ? (
            <EmptyState text={t("reports.empty")} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th scope="col">№</th>
                  <th scope="col">{t("reports.student")}</th>
                  <th scope="col">{t("reports.average")}</th>
                  <th scope="col">{t("reports.grades")}</th>
                  <th scope="col">{t("reports.attendance")}</th>
                  <th scope="col">{t("reports.absent")}</th>
                  <th scope="col">{t("reports.excused")}</th>
                  <th scope="col">{t("reports.late")}</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row, i) => (
                  <tr key={row.student}>
                    <td className="mono">{i + 1}</td>
                    <td>{row.full_name}</td>
                    <td className="mono">{num(row.average)}</td>
                    <td className="mono">{row.grades}</td>
                    <td className="mono">{num(row.attendance_percent, 0)}</td>
                    <td className="mono">{row.absent}</td>
                    <td className="mono">{row.excused}</td>
                    <td className="mono">{row.late}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td />
                  <th scope="row">{t("reports.summary")}</th>
                  <td className="mono">{num(data.summary.average)}</td>
                  <td />
                  <td className="mono">{num(data.summary.attendance_percent, 0)}</td>
                  <td colSpan={3} className={styles.status}>
                    {t("reports.lowAttendance")}: {data.summary.low_attendance} ·{" "}
                    {t("reports.lowAverage")}: {data.summary.low_average}
                  </td>
                </tr>
              </tfoot>
            </Table>
          )}
        </>
      )}
    </div>
  );
}

/** «Отчёты» of a teacher: the statement of an own course. */
export function TeacherReportsPage() {
  return (
    <section className={styles.page}>
      <h1>{t("reports.statement")}</h1>
      <StatementPanel />
    </section>
  );
}
