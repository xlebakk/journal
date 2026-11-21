import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useCourses, useTeachers } from "@/features/admin/groups/api";
import { useInvalidateSchedule, useRooms } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions, ScheduleIssues, SelectField, TextField } from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { issuesOf, useLessonTypes, warningsOf } from "./api";

/** A one-off lesson: consultation, mock test (SPEC §9). */
export function ExtraLessonDialog({
  open,
  today,
  onClose,
}: {
  open: boolean;
  today: string;
  onClose: (warnings: ScheduleWarning[]) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose([])} title={t("schedule.addLesson")}>
      {open && <ExtraLessonForm today={today} onClose={onClose} />}
    </Dialog>
  );
}

function ExtraLessonForm({
  today,
  onClose,
}: {
  today: string;
  onClose: (warnings: ScheduleWarning[]) => void;
}) {
  const courses = useCourses();
  const rooms = useRooms();
  const teachers = useTeachers();
  const lessonTypes = useLessonTypes();
  const invalidate = useInvalidateSchedule();
  const consultation = lessonTypes.data?.find((x) => x.short === "Конс")?.id ?? "";
  const [values, setValues] = useState({
    course: "",
    date: today,
    start_time: "10:00",
    end_time: "11:30",
    room: "",
    lesson_type: "",
    teacher: "",
  });
  const set = (name: keyof typeof values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [name]: e.target.value }));
  const create = useMutation({
    mutationFn: () =>
      api<unknown>("/admin/lessons", {
        method: "POST",
        body: {
          ...values,
          room: values.room || null,
          lesson_type: values.lesson_type || consultation || null,
          teacher: values.teacher || null,
        },
      }),
    onSuccess: async (data) => {
      await invalidate();
      onClose(warningsOf(data));
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  const { conflicts } = issuesOf(create.error);
  const fieldsError =
    create.error instanceof ApiError && Object.keys(create.error.fields).length > 0;
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <SelectField
        label={t("schedule.course")}
        value={values.course}
        onChange={set("course")}
        options={[
          { value: "", label: "—" },
          ...(courses.data ?? []).map((c) => ({
            value: c.id,
            label: `${c.group_name} · ${c.subject_name}`,
          })),
        ]}
      />
      <div className={styles.grid}>
        <TextField
          label={t("schedule.date")}
          type="date"
          value={values.date}
          onChange={set("date")}
        />
        <TextField
          label={t("schedule.start")}
          type="time"
          value={values.start_time}
          onChange={set("start_time")}
        />
        <TextField
          label={t("schedule.end")}
          type="time"
          value={values.end_time}
          onChange={set("end_time")}
          error={fieldError(create.error, "end_time")}
        />
        <SelectField
          label={t("schedule.roomFilter")}
          value={values.room}
          onChange={set("room")}
          options={[
            { value: "", label: t("schedule.noRoom") },
            ...(rooms.data ?? []).map((r) => ({ value: r.id, label: `${r.name} (${r.capacity})` })),
          ]}
        />
        <SelectField
          label={t("schedule.lessonType")}
          value={values.lesson_type || consultation}
          onChange={set("lesson_type")}
          options={[
            { value: "", label: "—" },
            ...(lessonTypes.data ?? []).map((x) => ({ value: x.id, label: x.name })),
          ]}
        />
        <SelectField
          label={t("schedule.teacher")}
          value={values.teacher}
          onChange={set("teacher")}
          options={[
            { value: "", label: "—" },
            ...(teachers.data ?? []).map((p) => ({ value: p.id, label: p.full_name })),
          ]}
        />
      </div>
      <ScheduleIssues conflicts={conflicts} />
      {create.error && !conflicts.length && !fieldsError && (
        <p className={styles.error} role="alert">
          {errorMessage(create.error)}
        </p>
      )}
      <DialogActions>
        <Button type="submit" variant="primary" disabled={create.isPending || !values.course}>
          {t("schedule.addLesson")}
        </Button>
        <Button onClick={() => onClose([])}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}
