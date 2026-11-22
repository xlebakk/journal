import { MessageSquare } from "lucide-react";
import { useState, type KeyboardEvent } from "react";

import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions, SelectField, TextField } from "@/shared/ui";

import {
  GRADABLE,
  isLow,
  journalApi,
  SCALE_RANGE,
  STATUS_CYCLE,
  type Attendance,
  type AttendanceStatus,
  type Grade,
  type Rules,
  type WorkTypeOption,
} from "./api";
import styles from "./Journal.module.css";
import { isPendingId } from "./offlinePatches";
import type { Action } from "./useSave";
import {
  addGradeAction,
  attendanceAction,
  deleteGradeAction,
  mark,
  statusFromKey,
  STATUS_NAME,
  type LessonRef,
} from "./actions";

type EditorProps = {
  lesson: LessonRef;
  rules: Rules;
  workTypes: WorkTypeOption[];
  student: { id: string; short_name: string; full_name: string };
  attendance?: Attendance;
  grades: Grade[];
  reason: string;
  isAdmin: boolean;
  busy: boolean;
  perform: (action: Action) => Promise<boolean>;
};

export function GradeInput({
  rules,
  disabled,
  label,
  onSubmit,
}: {
  rules: Rules;
  disabled: boolean;
  label: string;
  onSubmit: (value: number) => void;
}) {
  const [min, max] = SCALE_RANGE[rules.scale] ?? [0, 100];
  const [text, setText] = useState("");
  if (rules.scale !== "100") {
    // Small scales: big buttons with the values (SPEC §7.2).
    return (
      <div className={styles.valueButtons} role="group" aria-label={label}>
        {Array.from({ length: max - min + 1 }, (_, i) => min + i).map((value) => (
          <button
            key={value}
            type="button"
            disabled={disabled}
            className={styles.valueButton}
            onClick={() => onSubmit(value)}
          >
            {value}
          </button>
        ))}
      </div>
    );
  }
  const number = Number(text);
  const invalid = text !== "" && (!/^\d+$/.test(text) || number < min || number > max);
  const submit = () => {
    if (text === "" || invalid) return;
    onSubmit(number);
    setText("");
  };
  return (
    <input
      className={`mono ${styles.gradeInput}`}
      inputMode="numeric"
      pattern="[0-9]*"
      aria-label={label}
      aria-invalid={invalid || undefined}
      title={invalid ? t("journal.outOfRange", { min, max }) : t("journal.rangeHint", { min, max })}
      placeholder="+"
      disabled={disabled}
      value={text}
      maxLength={3}
      onChange={(e) => setText(e.target.value.trim())}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          submit();
        }
        if (e.key === "Escape") setText("");
      }}
      onBlur={submit}
    />
  );
}

function GradeDialog({
  grade,
  rules,
  workTypes,
  reason,
  perform,
  onClose,
}: {
  grade: Grade;
  rules: Rules;
  workTypes: WorkTypeOption[];
  reason: string;
  perform: (action: Action) => Promise<boolean>;
  onClose: () => void;
}) {
  const [min, max] = SCALE_RANGE[rules.scale] ?? [0, 100];
  const [value, setValue] = useState(String(grade.value));
  const [workType, setWorkType] = useState(grade.work_type);
  const [comment, setComment] = useState(grade.comment);
  const number = Number(value);
  const invalid = !/^\d+$/.test(value) || number < min || number > max;
  const save = async () => {
    const ok = await perform({
      run: () =>
        journalApi.updateGrade(grade.id, {
          version: grade.version,
          value: number,
          work_type: workType,
          comment,
          reason,
        }),
      undo: (result) => () =>
        journalApi.updateGrade(grade.id, {
          version: (result as Grade).version,
          value: grade.value,
          work_type: grade.work_type,
          comment: grade.comment,
          reason,
        }),
    });
    if (ok) onClose();
  };
  const remove = async () => {
    if (await perform(deleteGradeAction(grade, reason))) onClose();
  };
  if (isPendingId(grade.id)) {
    // Still in the offline queue: it can only be taken back.
    return (
      <div className={styles.form}>
        <p className={styles.note}>{t("offline.notSentGrade")}</p>
        <DialogActions>
          <Button variant="danger" onClick={() => void remove()}>
            {t("journal.deleteGrade")}
          </Button>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
        </DialogActions>
      </div>
    );
  }
  return (
    <div className={styles.form}>
      <TextField
        label={t("journal.grade")}
        inputMode="numeric"
        value={value}
        onChange={(e) => setValue(e.target.value.trim())}
        error={invalid ? t("journal.outOfRange", { min, max }) : undefined}
      />
      <SelectField
        label={t("journal.workType")}
        value={workType}
        onChange={(e) => setWorkType(e.target.value)}
        options={workTypes.map((w) => ({ value: w.id, label: `${w.name} ×${Number(w.weight)}` }))}
      />
      <TextField
        label={t("journal.comment")}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <DialogActions>
        <Button variant="primary" disabled={invalid} onClick={() => void save()}>
          {t("journal.save")}
        </Button>
        <Button variant="danger" onClick={() => void remove()}>
          {t("journal.deleteGrade")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </div>
  );
}

/** One student of a lesson: attendance, grades, comment (SPEC §7.2). */
export function StudentEditor(props: EditorProps) {
  const { lesson, rules, workTypes, student, attendance, grades, reason, isAdmin, busy, perform } =
    props;
  const [editing, setEditing] = useState<Grade | null>(null);
  const [commenting, setCommenting] = useState(false);
  const [comment, setComment] = useState("");
  const blocked = !lesson.editable || (lesson.needs_reason && !reason.trim());
  const status: AttendanceStatus = attendance?.status ?? "present";
  const gradable = GRADABLE.includes(status);
  const canAdd = !blocked && gradable && grades.length < rules.max_grades;

  const setStatus = (
    next: AttendanceStatus,
    extra: { late_minutes?: number | null; comment?: string } = {},
  ) =>
    perform(
      attendanceAction(
        lesson,
        student.id,
        attendance,
        { status: next, ...extra },
        reason,
        student.short_name,
      ),
    );

  const cycle = () => {
    const next = STATUS_CYCLE[(STATUS_CYCLE.indexOf(status) + 1) % STATUS_CYCLE.length]!;
    void setStatus(next);
  };
  const onKey = (event: KeyboardEvent) => {
    const next = statusFromKey(event);
    if (next && !blocked) {
      event.preventDefault();
      void setStatus(next);
    }
  };

  return (
    <div className={styles.studentRow}>
      <span className={styles.studentName}>{student.short_name}</span>
      <button
        type="button"
        className={`${styles.mark} ${styles[`mark_${status}`]} ${attendance ? "" : styles.unmarked} ${
          attendance && isPendingId(attendance.id) ? styles.pending : ""
        }`}
        aria-label={t("journal.statusCycle", { status: t(STATUS_NAME[status]) })}
        disabled={blocked || busy}
        onClick={cycle}
        onKeyDown={onKey}
      >
        {mark(status)}
      </button>
      {status === "late" && (
        <input
          className={`mono ${styles.lateInput}`}
          inputMode="numeric"
          aria-label={t("journal.lateMinutes")}
          placeholder={t("journal.lateMinutes")}
          defaultValue={attendance?.late_minutes ?? ""}
          disabled={blocked}
          onBlur={(e) => {
            const minutes = Number(e.target.value);
            if (
              e.target.value &&
              minutes >= 1 &&
              minutes <= 300 &&
              minutes !== attendance?.late_minutes
            ) {
              void setStatus("late", { late_minutes: minutes });
            }
          }}
        />
      )}
      <span className={styles.grades}>
        {grades.map((grade) => {
          const own = grade.mine || isAdmin;
          return (
            <button
              key={grade.id}
              type="button"
              className={`mono ${styles.gradeChip} ${isLow(grade.value, rules) ? styles.low : ""} ${
                isPendingId(grade.id) ? styles.pending : ""
              }`}
              title={
                isPendingId(grade.id)
                  ? t("offline.notSent")
                  : own
                    ? grade.comment || undefined
                    : t("journal.notYours", { name: grade.author_name })
              }
              disabled={blocked || !own}
              onClick={() => setEditing(grade)}
            >
              {grade.value}
            </button>
          );
        })}
        {canAdd && (
          <GradeInput
            rules={rules}
            disabled={busy}
            label={t("journal.addGrade", { name: student.short_name })}
            onSubmit={(value) =>
              void perform(
                addGradeAction(lesson, student.id, value, reason, undefined, student.short_name),
              )
            }
          />
        )}
      </span>
      <Button
        aria-label={t("journal.markComment")}
        title={attendance?.comment || t("journal.markComment")}
        disabled={blocked}
        onClick={() => {
          setComment(attendance?.comment ?? "");
          setCommenting(true);
        }}
      >
        <MessageSquare size={16} strokeWidth={1.5} aria-hidden="true" />
        {attendance?.comment && <span className="visually-hidden">{attendance.comment}</span>}
      </Button>

      <Dialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={student.full_name}
      >
        {editing && (
          <GradeDialog
            grade={editing}
            rules={rules}
            workTypes={workTypes}
            reason={reason}
            perform={perform}
            onClose={() => setEditing(null)}
          />
        )}
      </Dialog>
      <Dialog open={commenting} onOpenChange={setCommenting} title={t("journal.markComment")}>
        <div className={styles.form}>
          <TextField
            label={student.full_name}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <DialogActions>
            <Button
              variant="primary"
              onClick={async () => {
                if (
                  await setStatus(status, {
                    comment,
                    late_minutes: attendance?.late_minutes ?? null,
                  })
                )
                  setCommenting(false);
              }}
            >
              {t("journal.save")}
            </Button>
            <Button onClick={() => setCommenting(false)}>{t("common.cancel")}</Button>
          </DialogActions>
        </div>
      </Dialog>
    </div>
  );
}
