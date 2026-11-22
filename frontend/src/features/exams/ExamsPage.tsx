import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useMe } from "@/features/auth/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday, formatDate } from "@/shared/lib/week";
import { Button, EmptyState, RuledSkeleton, ScoreChart, SelectField, Table } from "@/shared/ui";

import { examsBase, percentText, useDynamics, useExams, type Exam } from "./api";
import { ExamForm } from "./ExamForm";

function subjectsOf(exams: Exam[]): { value: string; label: string }[] {
  const map = new Map(exams.map((e) => [e.subject, e.subject_name]));
  return [...map].map(([value, label]) => ({ value, label }));
}

/** The center's dynamics for a subject: mean % per test over time. */
function Dynamics({ subjects }: { subjects: { value: string; label: string }[] }) {
  const [picked, setPicked] = useState("");
  const subject = picked || subjects[0]?.value;
  const points = useDynamics(subject);
  if (subjects.length === 0) return null;
  const name = subjects.find((s) => s.value === subject)?.label ?? "";
  return (
    <section className={styles.section} aria-labelledby="exams-dynamics">
      <h2 id="exams-dynamics">{t("exams.dynamics")}</h2>
      <p className={styles.note}>{t("exams.dynamicsHint")}</p>
      <div className={styles.toolbar}>
        <SelectField
          label={t("exams.subject")}
          value={subject}
          onChange={(e) => setPicked(e.target.value)}
          options={subjects}
        />
      </div>
      {points.data && points.data.length > 0 && (
        <ScoreChart
          label={`${t("exams.dynamics")}: ${name}`}
          points={points.data
            .filter((p) => p.count > 0)
            .map((p) => ({
              key: p.exam,
              label: formatDate(p.date).slice(0, 5),
              percent: p.mean_percent === null ? null : Number(p.mean_percent),
              score: percentText(p.mean_percent),
            }))}
        />
      )}
    </section>
  );
}

/** «Пробные тесты»: a teacher's tests of own courses, all tests for the administrator. */
export function ExamsPage() {
  const me = useMe();
  const role = me.data?.active_role;
  const base = examsBase(role);
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const exams = useExams();
  const [creating, setCreating] = useState(false);
  const today = centerToday();
  const all = exams.data ?? [];
  const shown = subject ? all.filter((e) => e.subject === subject) : all;
  const subjects = subjectsOf(all);

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("exams.title")}</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>
          {t("exams.create")}
        </Button>
      </div>
      {subjects.length > 1 && (
        <div className={styles.toolbar}>
          <SelectField
            label={t("exams.subject")}
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            options={[{ value: "", label: t("exams.allSubjects") }, ...subjects]}
          />
        </div>
      )}
      {exams.isPending ? (
        <RuledSkeleton rows={5} />
      ) : exams.error ? (
        <p className={styles.error}>{errorMessage(exams.error)}</p>
      ) : shown.length === 0 ? (
        <EmptyState text={t("exams.empty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("exams.date")}</th>
              <th scope="col">{t("exams.name")}</th>
              <th scope="col">{t("exams.subject")}</th>
              <th scope="col">{t("exams.groups")}</th>
              <th scope="col">{t("exams.max")}</th>
              <th scope="col">{t("exams.results")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((exam) => (
              <tr key={exam.id}>
                <td className="mono">
                  {formatDate(exam.date)}
                  {exam.date > today && (
                    <span className={styles.status}> · {t("exams.upcoming")}</span>
                  )}
                </td>
                <td>
                  <Link to={`${base}/${exam.id}`}>{exam.title}</Link>
                </td>
                <td>{exam.subject_name}</td>
                <td>{exam.courses.map((c) => c.group_name).join(", ")}</td>
                <td className="mono">{exam.max_score}</td>
                <td className="mono">{exam.results_count}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {role === "admin" && <Dynamics subjects={subjects} />}
      {creating && (
        <ExamForm
          open
          onClose={() => setCreating(false)}
          onSaved={(exam) => navigate(`${base}/${exam.id}`)}
        />
      )}
    </section>
  );
}
