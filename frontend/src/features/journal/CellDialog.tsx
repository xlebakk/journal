import { useState, type FormEvent } from "react";

import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDayLong } from "@/shared/lib/week";
import { Button, Dialog, DialogActions, TextField } from "@/shared/ui";

import {
  GRADABLE,
  SCALE_RANGE,
  type Attendance,
  type Grade,
  type GridLesson,
  type RowStudent,
  type Rules,
} from "./api";
import {
  addGradeAction,
  attendanceAction,
  deleteGradeAction,
  mark,
  updateGradeAction,
} from "./actions";
import styles from "./Journal.module.css";
import { isPendingId } from "./offlinePatches";
import type { Action, SaveState } from "./useSave";

type Props = {
  lesson: GridLesson;
  student: RowStudent;
  attendance?: Attendance;
  grades: Grade[];
  rules: Rules;
  isAdmin: boolean;
  /** The reason already typed on this page for a closed window. */
  reason: string;
  onReason: (why: string) => void;
  perform: (action: Action) => Promise<boolean>;
  state: SaveState;
  onClose: () => void;
};

/**
 * One cell of the journal, after the eDonish grade window but simpler: points or «н», and a
 * remark — why the grade is what it is. Everything else (work type, lateness, several grades)
 * stays on the lesson page.
 */
function CellForm({
  lesson,
  student,
  attendance,
  grades,
  rules,
  isAdmin,
  reason,
  onReason,
  perform,
  state,
  onClose,
}: Props) {
  const [min, max] = SCALE_RANGE[rules.scale] ?? [0, 100];
  const own = [...grades].reverse().find((g) => g.mine || isAdmin);
  const others = grades.filter((g) => g !== own);
  const wasAbsent = attendance?.status === "absent";
  const [score, setScore] = useState(own ? String(own.value) : "");
  const [absent, setAbsent] = useState(wasAbsent);
  const [remark, setRemark] = useState((wasAbsent ? attendance?.comment : own?.comment) ?? "");
  const [why, setWhy] = useState(reason);
  const [saving, setSaving] = useState(false);
  const [failed, setFailed] = useState(false);
  const [problem, setProblem] = useState("");

  const number = Number(score);
  const invalid = score !== "" && (!/^\d+$/.test(score) || number < min || number > max);
  const needsWhy = lesson.needs_reason && !why.trim();

  const steps = (): Action[] | string => {
    const who = student.short_name;
    const list: Action[] = [];
    const setStatus = (status: "present" | "absent", comment: string) =>
      list.push(attendanceAction(lesson, student.id, attendance, { status, comment }, why, who));
    if (absent) {
      // An absent student has no grades: one's own go first, a colleague's stop the change.
      if (others.some((g) => !(g.mine || isAdmin))) return t("errors.has_grades");
      for (const grade of grades) list.push(deleteGradeAction(grade, why));
      if (!wasAbsent || (attendance?.comment ?? "") !== remark) setStatus("absent", remark);
      return list;
    }
    const gradable = !attendance || GRADABLE.includes(attendance.status);
    if (!gradable) setStatus("present", score === "" ? remark : "");
    if (score === "") {
      if (own) list.push(deleteGradeAction(own, why));
      return list;
    }
    if (own && !isPendingId(own.id)) {
      if (own.value !== number || own.comment !== remark) {
        list.push(updateGradeAction(own, { value: number, comment: remark }, why));
      }
      return list;
    }
    // A grade still waiting for the network can only be taken back and given again.
    if (own) list.push(deleteGradeAction(own, why));
    list.push(addGradeAction(lesson, student.id, number, why, undefined, who, remark));
    return list;
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (invalid || needsWhy || saving) return;
    const plan = steps();
    if (typeof plan === "string") return setProblem(plan);
    if (lesson.needs_reason) onReason(why);
    setSaving(true);
    setFailed(false);
    for (const action of plan) {
      if (!(await perform(action))) {
        setSaving(false);
        setFailed(true);
        return;
      }
    }
    onClose();
  };

  const error = problem || (failed && state.kind === "error" ? errorMessage(state.error) : "");
  return (
    <form className={styles.cellForm} onSubmit={(e) => void submit(e)} noValidate>
      <div className={styles.cellEntry}>
        <label className={styles.scoreField}>
          <span className={styles.label}>{t("journal.points", { min, max })}</span>
          <input
            className={styles.scoreInput}
            inputMode="numeric"
            pattern="[0-9]*"
            maxLength={3}
            // The window opens on a click into the cell: typing starts right away.
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
            disabled={absent}
            aria-invalid={invalid || undefined}
            value={score}
            onChange={(e) => {
              setScore(e.target.value.trim());
              setProblem("");
            }}
          />
        </label>
        <span className={styles.cellOr}>{t("journal.or")}</span>
        <button
          type="button"
          className={styles.absentToggle}
          aria-pressed={absent}
          aria-label={t("journal.markAbsent")}
          title={t("journal.markAbsent")}
          onClick={() => {
            setAbsent(!absent);
            setScore(absent ? (own ? String(own.value) : "") : "");
            setProblem("");
          }}
        >
          {mark("absent")}
        </button>
      </div>
      {invalid && (
        <p className={styles.error} role="alert">
          {t("journal.outOfRange", { min, max })}
        </p>
      )}
      {others.length > 0 && !absent && (
        <p className={styles.note}>
          {t("journal.otherGrades", {
            grades: others.map((g) => `${g.value} (${g.author_name})`).join(", "),
          })}
        </p>
      )}
      <label className={styles.textareaField}>
        <span className={styles.label}>{t("journal.remark")}</span>
        <textarea
          className={styles.textarea}
          rows={3}
          maxLength={300}
          placeholder={absent ? t("journal.remarkAbsentHint") : t("journal.remarkHint")}
          value={remark}
          onChange={(e) => setRemark(e.target.value)}
        />
      </label>
      {lesson.needs_reason && (
        <TextField
          label={t("journal.reasonField")}
          hint={t("journal.reasonShort")}
          value={why}
          onChange={(e) => setWhy(e.target.value)}
          required
        />
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      <DialogActions>
        <Button type="submit" variant="primary" disabled={invalid || needsWhy || saving}>
          {t("journal.save")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

export function CellDialog(props: Props & { subject: string }) {
  const { lesson, student, subject, onClose } = props;
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
      title={student.full_name}
      description={`${subject} · ${formatDayLong(lesson.date)}`}
    >
      <CellForm {...props} />
    </Dialog>
  );
}
