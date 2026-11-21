import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday } from "@/shared/lib/week";
import { Button, Checkbox, Dialog, DialogActions, SelectField, TextField } from "@/shared/ui";

import { useExamCourses, useInvalidateExams, type Exam, type ExamInput } from "./api";

type SectionDraft = { name: string; max: string };

function initial(exam: Exam | undefined) {
  return {
    title: exam?.title ?? "",
    date: exam?.date ?? centerToday(),
    max: String(exam?.max_score ?? 100),
    subject: exam?.subject ?? "",
    courses: exam?.courses.map((c) => c.id) ?? [],
    sections: exam?.sections.map((s) => ({ name: s.name, max: String(s.max_score) })) ?? [],
  };
}

/**
 * Create or edit a test: title, date, maximum, the courses (of one subject) and optional
 * sections whose maxima add up to the test maximum. Once results exist, the server keeps
 * the maximum, sections and subject.
 */
export function ExamForm({
  open,
  exam,
  onClose,
  onSaved,
}: {
  open: boolean;
  exam?: Exam;
  onClose: () => void;
  onSaved: (exam: Exam) => void;
}) {
  const courses = useExamCourses();
  const invalidate = useInvalidateExams();
  const [draft, setDraft] = useState(() => initial(exam));
  const locked = (exam?.results_count ?? 0) > 0;
  const subjects = new Map((courses.data ?? []).map((c) => [c.subject, c.subject_name]));
  const subject = draft.subject || courses.data?.[0]?.subject || "";
  const sameSubject = (courses.data ?? []).filter((c) => c.subject === subject);

  const save = useMutation({
    mutationFn: () => {
      const body: ExamInput = {
        title: draft.title.trim(),
        subject,
        date: draft.date,
        max_score: Number(draft.max),
        courses: draft.courses,
        sections: draft.sections
          .filter((s) => s.name.trim())
          .map((s) => ({ name: s.name.trim(), max_score: Number(s.max) })),
      };
      if (!exam) return api<Exam>("/exams", { method: "POST", body });
      const { max_score, sections, subject: subjectId, ...rest } = body;
      const patch = locked ? rest : { ...rest, max_score, sections, subject: subjectId };
      return api<Exam>(`/exams/${exam.id}`, {
        method: "PATCH",
        body: { ...patch, version: exam.version },
      });
    },
    onSuccess: async (saved) => {
      await invalidate();
      onSaved(saved);
    },
  });

  const setSection = (index: number, change: Partial<SectionDraft>) =>
    setDraft((d) => ({
      ...d,
      sections: d.sections.map((s, i) => (i === index ? { ...s, ...change } : s)),
    }));
  const toggleCourse = (id: string, on: boolean) =>
    setDraft((d) => ({
      ...d,
      courses: on ? [...d.courses, id] : d.courses.filter((c) => c !== id),
    }));
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const otherError =
    save.error &&
    !["title", "date", "max_score", "courses", "sections"].some((f) => fieldError(save.error, f));

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={exam ? exam.title : t("exams.create")}
    >
      <form className={styles.form} onSubmit={submit} noValidate>
        <TextField
          label={t("exams.name")}
          value={draft.title}
          onChange={(e) => setDraft({ ...draft, title: e.target.value })}
          error={fieldError(save.error, "title")}
        />
        <div className={styles.row}>
          <TextField
            label={t("exams.date")}
            type="date"
            value={draft.date}
            onChange={(e) => setDraft({ ...draft, date: e.target.value })}
            error={fieldError(save.error, "date")}
          />
          <TextField
            label={t("exams.max")}
            type="number"
            min={1}
            max={1000}
            inputMode="numeric"
            value={draft.max}
            disabled={locked}
            onChange={(e) => setDraft({ ...draft, max: e.target.value })}
            error={fieldError(save.error, "max_score")}
          />
        </div>
        <SelectField
          label={t("exams.subject")}
          value={subject}
          disabled={locked}
          onChange={(e) => setDraft({ ...draft, subject: e.target.value, courses: [] })}
          options={[...subjects].map(([value, label]) => ({ value, label }))}
        />
        <fieldset className={styles.section}>
          <legend className={styles.status}>{t("exams.courses")}</legend>
          {sameSubject.map((c) => (
            <Checkbox
              key={c.id}
              label={`${c.group_name} · ${c.teacher_name}`}
              checked={draft.courses.includes(c.id)}
              onChange={(e) => toggleCourse(c.id, e.target.checked)}
            />
          ))}
          {fieldError(save.error, "courses") && (
            <p className={styles.error}>{fieldError(save.error, "courses")}</p>
          )}
        </fieldset>
        <fieldset className={styles.section}>
          <legend className={styles.status}>{t("exams.sections")}</legend>
          <p className={styles.note}>{t("exams.sectionsHint")}</p>
          {draft.sections.map((section, i) => (
            <div key={i} className={styles.row}>
              <TextField
                label={t("exams.sectionName")}
                value={section.name}
                disabled={locked}
                onChange={(e) => setSection(i, { name: e.target.value })}
              />
              <TextField
                label={t("exams.sectionMax")}
                type="number"
                min={1}
                inputMode="numeric"
                value={section.max}
                disabled={locked}
                onChange={(e) => setSection(i, { max: e.target.value })}
              />
              {!locked && (
                <Button
                  onClick={() =>
                    setDraft((d) => ({ ...d, sections: d.sections.filter((_, j) => j !== i) }))
                  }
                >
                  {t("exams.removeSection")}
                </Button>
              )}
            </div>
          ))}
          {!locked && (
            <p>
              <Button
                onClick={() =>
                  setDraft((d) => ({ ...d, sections: [...d.sections, { name: "", max: "" }] }))
                }
              >
                {t("exams.addSection")}
              </Button>
            </p>
          )}
          {fieldError(save.error, "sections") && (
            <p className={styles.error}>{fieldError(save.error, "sections")}</p>
          )}
        </fieldset>
        {otherError && (
          <p className={styles.error} role="alert">
            {errorMessage(save.error)}
          </p>
        )}
        <DialogActions>
          <Button
            type="submit"
            variant="primary"
            disabled={save.isPending || !draft.title.trim() || draft.courses.length === 0}
          >
            {t("exams.save")}
          </Button>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
