import { useState } from "react";
import { useSearchParams } from "react-router";

import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import { formatDate, formatDayLong } from "@/shared/lib/week";
import { Button, Dialog, DialogActions, EmptyState, RuledSkeleton, SelectField } from "@/shared/ui";

import { useStudentGrades, type StudentGrade, type StudentGrades } from "./api";
import styles from "./Student.module.css";

function GradeDetails({ grade, onClose }: { grade: StudentGrade | null; onClose: () => void }) {
  return (
    <Dialog
      open={grade !== null}
      onOpenChange={(open) => !open && onClose()}
      title={
        grade ? `${grade.subject_name}: ${t("student.gradeTitle", { value: grade.value })}` : ""
      }
    >
      {grade && (
        <>
          <dl className={styles.facts}>
            <dt>{t("student.date")}</dt>
            <dd>{formatDayLong(grade.date)}</dd>
            <dt>{t("student.topic")}</dt>
            <dd>{grade.topic || "—"}</dd>
            <dt>{t("student.lessonType")}</dt>
            <dd>{grade.lesson_type_short ?? "—"}</dd>
            <dt>{t("student.workType")}</dt>
            <dd>{grade.work_type_name}</dd>
            <dt>{t("student.weight")}</dt>
            <dd className="mono">×{Number(grade.weight)}</dd>
            <dt>{t("student.teacherComment")}</dt>
            <dd>{grade.comment || "—"}</dd>
          </dl>
          <DialogActions>
            <Button onClick={onClose}>{t("common.close")}</Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  );
}

function GradeButton({
  grade,
  onOpen,
}: {
  grade: StudentGrade;
  onOpen: (g: StudentGrade) => void;
}) {
  return (
    <button
      type="button"
      className={`${styles.gradeButton} ${grade.low ? styles.low : ""}`}
      aria-label={`${grade.value}, ${grade.subject_name}, ${formatDayLong(grade.date)}`}
      onClick={() => onOpen(grade)}
    >
      {grade.value}
    </button>
  );
}

/** Desktop: subjects × dates with the weighted average at the end of each row. */
function GradesTable({ data, onOpen }: { data: StudentGrades; onOpen: (g: StudentGrade) => void }) {
  const dates = [...new Set(data.courses.flatMap((c) => c.grades.map((g) => g.date)))].sort();
  return (
    <div className={styles.scroller}>
      <table className={styles.gradesTable}>
        <thead>
          <tr>
            <th scope="col" className={styles.subjectCell}>
              {t("student.subject")}
            </th>
            {dates.map((d) => (
              <th key={d} scope="col">
                {d.slice(8, 10)}.{d.slice(5, 7)}
              </th>
            ))}
            <th scope="col" className={styles.averageCell}>
              {t("student.average")}
            </th>
          </tr>
        </thead>
        <tbody>
          {data.courses.map((course) => (
            <tr key={course.course}>
              <th scope="row" className={styles.subjectCell}>
                {course.subject_name}
                <span className={styles.meta}> · {course.group_name}</span>
              </th>
              {dates.map((d) => (
                <td key={d}>
                  {course.grades
                    .filter((g) => g.date === d)
                    .map((g) => (
                      <GradeButton key={g.id} grade={g} onOpen={onOpen} />
                    ))}
                </td>
              ))}
              <td className={`${styles.averageCell} ${course.low ? styles.low : ""}`}>
                {course.average ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Phone: a list of subjects, inside — grades by date. */
function GradesList({ data, onOpen }: { data: StudentGrades; onOpen: (g: StudentGrade) => void }) {
  return (
    <div>
      {data.courses.map((course) => (
        <details key={course.course} className={styles.subjectBlock}>
          <summary>
            <span>{course.subject_name}</span>
            <span className={`mono ${course.low ? styles.low : ""}`}>{course.average ?? "—"}</span>
          </summary>
          <ul className={styles.list}>
            {course.grades.map((g) => (
              <li key={g.id}>
                <span className={styles.meta}>{formatDate(g.date)}</span>
                <GradeButton grade={g} onOpen={onOpen} />
                <span className={styles.meta}>{g.work_type_name}</span>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}

/** «Оценки» (SPEC §6.3). No ranks and nothing about other students. */
export function GradesPage() {
  const [params, setParams] = useSearchParams();
  const term = params.get("term") || undefined;
  const grades = useStudentGrades(term);
  const phone = useMediaQuery("(max-width: 599px)");
  const [open, setOpen] = useState<StudentGrade | null>(null);
  const data = grades.data;

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("student.grades")}</h1>
        {data && (
          <SelectField
            label={t("student.period")}
            value={data.period}
            onChange={(e) =>
              setParams(e.target.value ? { term: e.target.value } : {}, { replace: true })
            }
            options={[
              ...data.terms.map((x) => ({ value: x.id, label: x.name })),
              { value: "year", label: t("student.wholeYear") },
            ]}
          />
        )}
      </div>
      {grades.isPending ? (
        <RuledSkeleton rows={6} />
      ) : grades.error || !data ? (
        <p className={styles.error}>{errorMessage(grades.error)}</p>
      ) : data.courses.every((c) => c.grades.length === 0) ? (
        <EmptyState text={t("student.noGrades")} />
      ) : phone ? (
        <GradesList data={data} onOpen={setOpen} />
      ) : (
        <GradesTable data={data} onOpen={setOpen} />
      )}
      <GradeDetails grade={open} onClose={() => setOpen(null)} />
    </section>
  );
}
