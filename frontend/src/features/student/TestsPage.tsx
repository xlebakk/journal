import { useQuery } from "@tanstack/react-query";

import { percentText, scoreText } from "@/features/exams/api";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, ScoreChart, Table } from "@/shared/ui";

import styles from "./Student.module.css";

type SubjectExams = Schemas["StudentSubjectExams"];

function change(value: string | null): string {
  if (value === null) return "—";
  const n = Number(value);
  const text = Math.abs(n).toLocaleString("ru-RU", { maximumFractionDigits: 1 });
  return n > 0 ? `+${text}` : n < 0 ? `−${text}` : "0";
}

function SubjectBlock({ subject }: { subject: SubjectExams }) {
  const target = subject.target_percent;
  return (
    <section className={styles.section} aria-labelledby={`tests-${subject.subject}`}>
      <div className={styles.titleRow}>
        <h2 id={`tests-${subject.subject}`}>{subject.subject_name}</h2>
        <span className={styles.meta}>
          {target === null
            ? t("studentTests.noTarget")
            : t("studentTests.target", { percent: target })}
        </span>
      </div>
      <ScoreChart
        label={t("studentTests.chartLabel", { subject: subject.subject_name })}
        target={target}
        targetLabel={target === null ? undefined : t("studentTests.target", { percent: target })}
        points={subject.exams.map((e) => ({
          key: e.exam,
          label: formatDate(e.date).slice(0, 5),
          percent: e.percent === null ? null : Number(e.percent),
          score: e.was_absent ? t("studentTests.absent") : scoreText(e.total, e.max_score),
        }))}
      />
      <Table>
        <thead>
          <tr>
            <th scope="col">{t("studentTests.date")}</th>
            <th scope="col">{t("studentTests.test")}</th>
            <th scope="col" className={styles.number}>
              {t("studentTests.score")}
            </th>
            <th scope="col" className={styles.number}>
              {t("studentTests.percent")}
            </th>
            <th scope="col" className={styles.number}>
              <span aria-hidden="true">{t("studentTests.changeShort")}</span>
              <span className="visually-hidden">{t("studentTests.change")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {subject.exams.map((e) => {
            const below = target !== null && e.percent !== null && Number(e.percent) < target;
            return (
              <tr key={e.exam}>
                {/* The year is the school year; dd.mm keeps the table within a phone. */}
                <td className={styles.number}>{formatDate(e.date).slice(0, 5)}</td>
                <td>
                  {e.title}
                  {e.sections.length > 0 && (
                    <span className={styles.meta}>
                      {" · "}
                      {e.sections.map((s) => `${s.name} ${s.score}/${s.max_score}`).join(", ")}
                    </span>
                  )}
                </td>
                <td className={styles.number}>
                  {e.was_absent ? t("studentTests.absent") : scoreText(e.total, e.max_score)}
                </td>
                <td className={`${styles.number} ${below ? styles.low : ""}`}>
                  {percentText(e.percent)}
                </td>
                <td className={styles.number}>{change(e.change)}</td>
              </tr>
            );
          })}
        </tbody>
      </Table>
    </section>
  );
}

/** «Пробные тесты» (SPEC §6.4): per subject, results in % with the goal line. */
export function TestsPage() {
  const exams = useQuery({
    queryKey: ["student", "exams"],
    queryFn: () => api<SubjectExams[]>("/student/exams"),
  });
  return (
    <section className={styles.page}>
      <h1>{t("studentTests.title")}</h1>
      {exams.isPending ? (
        <RuledSkeleton rows={6} />
      ) : exams.error ? (
        <p className={styles.error}>{errorMessage(exams.error)}</p>
      ) : exams.data.length === 0 ? (
        <EmptyState text={t("studentTests.empty")} />
      ) : (
        exams.data.map((subject) => <SubjectBlock key={subject.subject} subject={subject} />)
      )}
    </section>
  );
}
