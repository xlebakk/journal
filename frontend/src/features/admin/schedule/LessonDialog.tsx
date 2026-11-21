import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useTeachers } from "@/features/admin/groups/api";
import { useInvalidateSchedule, useRooms, type Lesson } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";
import {
  Button,
  Dialog,
  DialogActions,
  lessonMarks,
  ScheduleIssues,
  SelectField,
  TextField,
} from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { issuesOf, warningsOf } from "./api";

type Mode = "cancel" | "move" | "substitute";

const STATUS: Record<string, MessageKey> = {
  planned: "schedule.statusPlanned",
  conducted: "schedule.statusConducted",
  cancelled: "schedule.statusCancelled",
};

/** One lesson and its exceptions (SPEC §9). Every change sends `version` (SPEC §10.12). */
export function LessonDialog({ lesson, onClose }: { lesson: Lesson | null; onClose: () => void }) {
  return (
    <Dialog
      open={lesson !== null}
      onOpenChange={(open) => !open && onClose()}
      title={lesson ? `${lesson.subject_name} · ${lesson.group_name}` : t("schedule.lessonTitle")}
    >
      {lesson && (
        <LessonActions key={`${lesson.id}:${lesson.version}`} lesson={lesson} onClose={onClose} />
      )}
    </Dialog>
  );
}

function LessonActions({ lesson, onClose }: { lesson: Lesson; onClose: () => void }) {
  const rooms = useRooms();
  const teachers = useTeachers();
  const invalidate = useInvalidateSchedule();
  const [mode, setMode] = useState<Mode | null>(null);
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(lesson.date);
  const [start, setStart] = useState(hhmm(lesson.start_time));
  const [end, setEnd] = useState(hhmm(lesson.end_time));
  const [room, setRoom] = useState(lesson.room ?? "");
  const [teacher, setTeacher] = useState("");
  const [warnings, setWarnings] = useState<ScheduleWarning[]>([]);

  const act = useMutation({
    mutationFn: (action: "cancel" | "restore" | "move" | "substitute") => {
      const version = lesson.version;
      const body =
        action === "cancel"
          ? { version, reason }
          : action === "move"
            ? { version, date, start_time: start, end_time: end, room: room || null }
            : action === "substitute"
              ? { version, teacher: teacher || null }
              : { version };
      return api<unknown>(`/admin/lessons/${lesson.id}/${action}`, { method: "POST", body });
    },
    onSuccess: async (data) => {
      await invalidate();
      const found = warningsOf(data);
      if (found.length) setWarnings(found);
      else onClose();
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mode) act.mutate(mode);
  };
  const { conflicts } = issuesOf(act.error);
  const genericError =
    act.error &&
    !conflicts.length &&
    !(act.error instanceof ApiError && Object.keys(act.error.fields).length)
      ? errorMessage(act.error)
      : null;
  const editable = lesson.status === "planned";

  return (
    <div className={styles.form}>
      <dl className={styles.facts}>
        <dt>{t("schedule.date")}</dt>
        <dd>
          {formatDayLong(lesson.date)},{" "}
          <span className="mono">
            {hhmm(lesson.start_time)}–{hhmm(lesson.end_time)}
          </span>
        </dd>
        <dt>{t("schedule.roomFilter")}</dt>
        <dd>{lesson.room_name ?? t("schedule.noRoom")}</dd>
        <dt>{t("schedule.teacher")}</dt>
        <dd>{lesson.teacher_name}</dd>
        <dt>{t("schedule.status")}</dt>
        <dd>
          {t(STATUS[lesson.status] ?? "schedule.statusPlanned")}
          {lesson.cancel_reason && <> · {lesson.cancel_reason}</>}
        </dd>
        {lessonMarks(lesson).map((mark) => (
          <dd key={mark.text}>{mark.text}</dd>
        ))}
      </dl>

      {editable && (
        <div className={styles.tabs} role="tablist">
          {(
            [
              ["cancel", "schedule.cancel"],
              ["move", "schedule.move"],
              ["substitute", "schedule.substituteAction"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={mode === value}
              className={styles.tab}
              onClick={() => {
                act.reset();
                setMode(value);
              }}
            >
              {t(label)}
            </button>
          ))}
        </div>
      )}

      {editable && mode && (
        <form className={styles.form} onSubmit={submit} noValidate>
          {mode === "cancel" && (
            <TextField
              label={t("schedule.reason")}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              error={fieldError(act.error, "reason")}
              required
            />
          )}
          {mode === "move" && (
            <div className={styles.grid}>
              <TextField
                label={t("schedule.date")}
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
              <TextField
                label={t("schedule.start")}
                type="time"
                value={start}
                onChange={(e) => setStart(e.target.value)}
              />
              <TextField
                label={t("schedule.end")}
                type="time"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                error={fieldError(act.error, "end_time")}
              />
              <SelectField
                label={t("schedule.roomFilter")}
                value={room}
                onChange={(e) => setRoom(e.target.value)}
                options={[
                  { value: "", label: t("schedule.noRoom") },
                  ...(rooms.data ?? []).map((r) => ({
                    value: r.id,
                    label: `${r.name} (${r.capacity})`,
                  })),
                ]}
              />
            </div>
          )}
          {mode === "substitute" && (
            <SelectField
              label={t("schedule.teacher")}
              value={teacher}
              onChange={(e) => setTeacher(e.target.value)}
              options={[
                { value: "", label: t("schedule.substituteReset") },
                ...(teachers.data ?? [])
                  .filter((p) => p.id !== lesson.teacher)
                  .map((p) => ({ value: p.id, label: p.full_name })),
              ]}
            />
          )}
          <ScheduleIssues conflicts={conflicts} />
          {genericError && (
            <p className={styles.error} role="alert">
              {genericError}
            </p>
          )}
          <DialogActions>
            <Button
              type="submit"
              variant="primary"
              disabled={act.isPending || (mode === "cancel" && !reason.trim())}
            >
              {t(
                mode === "cancel"
                  ? "schedule.cancel"
                  : mode === "move"
                    ? "schedule.move"
                    : "schedule.substituteAction",
              )}
            </Button>
            <Button onClick={onClose}>{t("common.close")}</Button>
          </DialogActions>
        </form>
      )}

      {lesson.status === "cancelled" && (
        <>
          <ScheduleIssues conflicts={conflicts} />
          {genericError && (
            <p className={styles.error} role="alert">
              {genericError}
            </p>
          )}
          <DialogActions>
            <Button
              variant="primary"
              onClick={() => act.mutate("restore")}
              disabled={act.isPending}
            >
              {t("schedule.restore")}
            </Button>
            <Button onClick={onClose}>{t("common.close")}</Button>
          </DialogActions>
        </>
      )}

      {warnings.length > 0 && (
        <>
          <ScheduleIssues warnings={warnings} />
          <DialogActions>
            <Button variant="primary" onClick={onClose}>
              {t("common.close")}
            </Button>
          </DialogActions>
        </>
      )}
    </div>
  );
}
