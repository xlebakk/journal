import { useState } from "react";
import { Link, useParams } from "react-router";

import { percentText, scoreText } from "@/features/exams/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { canPrint } from "@/platform";
import { t } from "@/shared/i18n";
import { centerToday, formatDate } from "@/shared/lib/week";
import { Button, RuledSkeleton, Table, TextField } from "@/shared/ui";

import { num, useStudentSummary } from "./api";
import local from "./Reports.module.css";

/** «Сводная ведомость ученика» for parents: one printed sheet (SPEC §8.8). */
export function StudentSummaryPage() {
  const { id = "" } = useParams();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const summary = useStudentSummary(id, { from: from || undefined, to: to || undefined });
  if (summary.isPending) return <RuledSkeleton rows={8} />;
  if (summary.error || !summary.data) {
    return <p className={styles.error}>{errorMessage(summary.error)}</p>;
  }
  const data = summary.data;
  return (
    <section className={`${styles.page} ${local.sheet}`}>
      <div className={`${styles.toolbar} ${styles.noPrint}`}>
        <Link to={`/admin/users/${id}`}>{t("common.back")}</Link>
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
        {canPrint && (
          <Button variant="primary" onClick={() => window.print()}>
            {t("reports.print")}
          </Button>
        )}
      </div>
      <header>
        <p className={styles.status}>{t("reports.summaryTitle")}</p>
        <h1 className={local.name}>{data.student.full_name}</h1>
        <dl className={styles.facts}>
          <dt>{t("reports.group")}</dt>
          <dd>{data.student.groups.join(", ") || "—"}</dd>
          <dt>{t("reports.period")}</dt>
          <dd>
            {data.year_name} ·{" "}
            {t("reports.periodLine", { from: formatDate(data.first), to: formatDate(data.last) })}
          </dd>
          {data.student.parent_name && (
            <>
              <dt>{t("reports.parent")}</dt>
              <dd>{data.student.parent_name}</dd>
            </>
          )}
          {data.student.target && (
            <>
              <dt>{t("reports.goal")}</dt>
              <dd>{data.student.target}</dd>
            </>
          )}
        </dl>
      </header>
      <h2>{t("reports.subjects")}</h2>
      <Table>
        <thead>
          <tr>
            <th scope="col">{t("reports.subject")}</th>
            <th scope="col">{t("reports.teacher")}</th>
            <th scope="col">{t("reports.average")}</th>
            <th scope="col">{t("reports.attendance")}</th>
            <th scope="col">{t("reports.absent")}</th>
            <th scope="col">{t("reports.excused")}</th>
            <th scope="col">{t("reports.late")}</th>
          </tr>
        </thead>
        <tbody>
          {data.subjects.map((s) => (
            <tr key={`${s.group_name}-${s.subject_name}`}>
              <td>{s.subject_name}</td>
              <td>{s.teacher_name}</td>
              <td className="mono">{num(s.average)}</td>
              <td className="mono">{num(s.attendance_percent, 0)}</td>
              <td className="mono">{s.absent}</td>
              <td className="mono">{s.excused}</td>
              <td className="mono">{s.late}</td>
            </tr>
          ))}
        </tbody>
      </Table>
      {data.exams.length > 0 && (
        <>
          <h2>{t("reports.exams")}</h2>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("exams.date")}</th>
                <th scope="col">{t("reports.subject")}</th>
                <th scope="col">{t("exams.name")}</th>
                <th scope="col">{t("studentTests.score")}</th>
                <th scope="col">{t("studentTests.percent")}</th>
              </tr>
            </thead>
            <tbody>
              {data.exams.map((e) => (
                <tr key={`${e.subject_name}-${e.date}-${e.title}`}>
                  <td className="mono">{formatDate(e.date)}</td>
                  <td>{e.subject_name}</td>
                  <td>{e.title}</td>
                  <td className="mono">
                    {e.was_absent ? t("studentTests.absent") : scoreText(e.total, e.max_score)}
                  </td>
                  <td className="mono">
                    {percentText(e.percent)}
                    {e.target_percent !== null && (
                      <span className={styles.status}>
                        {" "}
                        · {t("reports.examGoal", { percent: e.target_percent })}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
      <p className={styles.status}>{t("reports.printedOn", { date: formatDate(centerToday()) })}</p>
    </section>
  );
}
