import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";

import { useCourses, useTeachers } from "@/features/admin/groups/api";
import { useInvalidateSchedule } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { weekdayNames } from "@/shared/lib/week";
import { Button, DialogActions, ScheduleIssues, SelectField, TextField } from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { issuesOf, useLessonTypes, warningsOf } from "./api";

type Pair = { start: string; end: string };
type Availability = {
  group_busy: (Pair & { subject: string })[];
  free_pairs: Pair[];
  rooms: { id: string; name: string; capacity: number; fits: boolean }[];
  teachers: { id: string; full_name: string }[];
};

/**
 * Stage 19: a lesson or a template slot built step by step. Each step opens when the one above
 * is filled, and offers only what is free: pairs when the group and its teacher are both free,
 * rooms nobody holds at that time. The server still checks every conflict on save.
 */
export function LessonWizard({
  mode,
  today,
  presetDate,
  presetTime,
  presetGroup,
  onDone,
  onCancel,
}: {
  /** "lesson": one date (an extra lesson); "slot": a weekday of the week template. */
  mode: "lesson" | "slot";
  today: string;
  /** A free place clicked in the grid: its day and the start of its row. */
  presetDate?: string;
  presetTime?: string;
  presetGroup?: string;
  onDone: (warnings: ScheduleWarning[]) => void;
  onCancel: () => void;
}) {
  const courses = useCourses();
  const lessonTypes = useLessonTypes();
  const invalidate = useInvalidateSchedule();
  const [group, setGroup] = useState(presetGroup ?? "");
  const [course, setCourse] = useState("");
  const [date, setDate] = useState(presetDate || today);
  const [weekday, setWeekday] = useState("");
  const [validFrom, setValidFrom] = useState(today);
  const [validTo, setValidTo] = useState("");
  const [time, setTime] = useState<Pair | null>(null);
  const [custom, setCustom] = useState(false);
  const [room, setRoom] = useState<string | null>(null);
  const [lessonType, setLessonType] = useState("");
  const [teacher, setTeacher] = useState("");

  const groups = useMemo(() => {
    const seen = new Map<string, string>();
    for (const c of courses.data ?? []) seen.set(c.group, c.group_name);
    return [...seen].sort((a, b) => a[1].localeCompare(b[1]));
  }, [courses.data]);
  const groupCourses = (courses.data ?? []).filter((c) => c.group === group);
  const chosen = groupCourses.find((c) => c.id === course);
  // Stage 19: a one-off lesson may be taught by any teacher of the subject.
  const subjectTeachers = useTeachers(mode === "lesson" ? chosen?.subject : undefined);
  const teacherId = mode === "lesson" ? teacher || chosen?.teacher || "" : "";
  const when = mode === "lesson" ? date : weekday;
  const shift = mode === "lesson" ? 1 : 0;

  // The free pairs do not depend on the time; the last answer for this course and day holds them.
  const lastFree = useQuery({
    queryKey: [
      "admin",
      "availability",
      "pairs",
      course,
      teacherId,
      mode === "lesson" ? date : weekday,
      validFrom,
      validTo,
    ],
    queryFn: () =>
      api<Availability>("/admin/availability", {
        query:
          mode === "lesson"
            ? { course, date, teacher: teacherId || undefined }
            : { course, weekday, valid_from: validFrom, valid_to: validTo || undefined },
      }),
    enabled: Boolean(course && (mode === "lesson" ? date : weekday)),
    staleTime: 0,
  }).data;
  const query =
    mode === "lesson"
      ? { course, date, teacher: teacherId || undefined }
      : { course, weekday, valid_from: validFrom, valid_to: validTo || undefined };
  // The row clicked in the grid: its pair is taken as soon as it turns out to be free.
  const presetPair =
    !time && !custom && presetTime
      ? lastFree?.free_pairs.find((p) => p.start === presetTime)
      : undefined;
  const picked = time ?? presetPair ?? null;
  const timed = picked && picked.start && picked.end && picked.start < picked.end ? picked : null;
  const free = useQuery({
    queryKey: ["admin", "availability", query, timed],
    queryFn: () =>
      api<Availability>("/admin/availability", {
        query: { ...query, start: timed?.start, end: timed?.end },
      }),
    enabled: Boolean(course && when),
    staleTime: 0,
  });
  const data = free.data;

  // A change above clears the choices below it.
  const pickGroup = (value: string) => {
    setGroup(value);
    setCourse("");
    setTime(null);
    setRoom(null);
  };
  const pickCourse = (value: string) => {
    setCourse(value);
    setTeacher("");
    setTime(null);
    setRoom(null);
  };
  const pickWhen = (apply: () => void) => {
    apply();
    setTime(null);
    setRoom(null);
  };

  const save = useMutation({
    mutationFn: () =>
      mode === "lesson"
        ? api<unknown>("/admin/lessons", {
            method: "POST",
            body: {
              course,
              date,
              start_time: timed!.start,
              end_time: timed!.end,
              room: room || null,
              lesson_type: lessonType || null,
              // The course's own teacher is stored as no substitution.
              teacher: teacher && teacher !== chosen?.teacher ? teacher : null,
            },
          })
        : api<unknown>("/admin/slots", {
            method: "POST",
            body: {
              course,
              weekday: Number(weekday),
              start_time: timed!.start,
              end_time: timed!.end,
              room: room || null,
              lesson_type: lessonType || null,
              valid_from: validFrom,
              valid_to: validTo || null,
            },
          }),
    onSuccess: async (data) => {
      await invalidate();
      onDone(warningsOf(data));
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (timed && room !== null) save.mutate();
  };
  const { conflicts } = issuesOf(save.error);
  const fieldsError = save.error instanceof ApiError && Object.keys(save.error.fields).length > 0;

  return (
    <form className={styles.wizard} onSubmit={submit} noValidate>
      <Step n={1} title={t("schedule.stepGroup")}>
        <SelectField
          label={t("schedule.group")}
          value={group}
          onChange={(e) => pickGroup(e.target.value)}
          options={[
            { value: "", label: "—" },
            ...groups.map(([id, name]) => ({ value: id, label: name })),
          ]}
        />
      </Step>

      {group && (
        <Step n={2} title={t("schedule.stepSubject")}>
          <SelectField
            label={t("schedule.subject")}
            value={course}
            onChange={(e) => pickCourse(e.target.value)}
            options={[
              { value: "", label: "—" },
              ...groupCourses.map((c) => ({ value: c.id, label: c.subject_name })),
            ]}
          />
          {chosen && mode === "slot" && (
            <p className={styles.note}>
              {t("schedule.teacherIs", { name: chosen.teacher_info.short_name })}
            </p>
          )}
        </Step>
      )}

      {course && mode === "lesson" && (
        <Step n={3} title={t("schedule.stepTeacher")}>
          <SelectField
            label={t("schedule.teacher")}
            value={teacherId}
            onChange={(e) => {
              setTeacher(e.target.value);
              setTime(null);
              setRoom(null);
            }}
            options={[
              // The course's teacher even if their card lacks the subject.
              ...(chosen && !(subjectTeachers.data ?? []).some((p) => p.id === chosen.teacher)
                ? [{ id: chosen.teacher, full_name: chosen.teacher_info.short_name }]
                : []),
              ...(subjectTeachers.data ?? []),
            ]
              .slice()
              // The course's own teacher first.
              .sort((a, b) => Number(b.id === chosen?.teacher) - Number(a.id === chosen?.teacher))
              .map((p) => ({
                value: p.id,
                label:
                  p.id === chosen?.teacher
                    ? `${p.full_name} — ${t("schedule.courseTeacher")}`
                    : p.full_name,
              }))}
          />
        </Step>
      )}

      {course && (
        <Step
          n={3 + shift}
          title={mode === "lesson" ? t("schedule.stepDate") : t("schedule.stepWeekday")}
        >
          {mode === "lesson" ? (
            <TextField
              label={t("schedule.date")}
              type="date"
              value={date}
              onChange={(e) => pickWhen(() => setDate(e.target.value))}
            />
          ) : (
            <div className={styles.grid}>
              <SelectField
                label={t("schedule.weekday")}
                value={weekday}
                onChange={(e) => pickWhen(() => setWeekday(e.target.value))}
                options={[
                  { value: "", label: "—" },
                  ...weekdayNames().map((name, i) => ({ value: String(i + 1), label: name })),
                ]}
              />
              <TextField
                label={t("schedule.validFrom")}
                type="date"
                value={validFrom}
                onChange={(e) => pickWhen(() => setValidFrom(e.target.value))}
              />
              <TextField
                label={t("schedule.validTo")}
                type="date"
                hint={t("schedule.validToHint")}
                value={validTo}
                onChange={(e) => pickWhen(() => setValidTo(e.target.value))}
              />
            </div>
          )}
        </Step>
      )}

      {course && when && (
        <Step n={4 + shift} title={t("schedule.stepTime")}>
          {data && data.group_busy.length > 0 && (
            <p className={styles.note}>
              {t("schedule.groupBusy", {
                list: data.group_busy.map((b) => `${b.start}–${b.end} ${b.subject}`).join(", "),
              })}
            </p>
          )}
          {data && data.free_pairs.length > 0 && (
            <div className={styles.chips} role="group" aria-label={t("schedule.freePairs")}>
              {data.free_pairs.map((pair) => (
                <button
                  key={pair.start}
                  type="button"
                  className={styles.chip}
                  aria-pressed={!custom && picked?.start === pair.start && picked.end === pair.end}
                  onClick={() => {
                    setCustom(false);
                    setTime(pair);
                    setRoom(null);
                  }}
                >
                  {pair.start}–{pair.end}
                </button>
              ))}
              <button
                type="button"
                className={styles.chip}
                aria-pressed={custom}
                onClick={() => {
                  setCustom(true);
                  setTime({ start: "", end: "" });
                  setRoom(null);
                }}
              >
                {t("schedule.otherTime")}
              </button>
            </div>
          )}
          {data && data.free_pairs.length === 0 && !custom && (
            <p className={styles.note}>{t("schedule.noFreePairs")}</p>
          )}
          {(custom || (data && data.free_pairs.length === 0)) && (
            <div className={styles.grid}>
              <TextField
                label={t("schedule.start")}
                type="time"
                value={time?.start ?? ""}
                onChange={(e) => {
                  setTime({ start: e.target.value, end: time?.end ?? "" });
                  setRoom(null);
                }}
              />
              <TextField
                label={t("schedule.end")}
                type="time"
                value={time?.end ?? ""}
                onChange={(e) => {
                  setTime({ start: time?.start ?? "", end: e.target.value });
                  setRoom(null);
                }}
              />
            </div>
          )}
        </Step>
      )}

      {timed && data && (
        <Step n={5 + shift} title={t("schedule.stepRoom")}>
          {data.rooms.length === 0 && <p className={styles.note}>{t("schedule.noFreeRooms")}</p>}
          <div className={styles.chips} role="group" aria-label={t("schedule.freeRooms")}>
            {data.rooms.map((r) => (
              <button
                key={r.id}
                type="button"
                className={styles.chip}
                aria-pressed={room === r.id}
                title={r.fits ? undefined : t("schedule.roomSmall", { capacity: r.capacity })}
                onClick={() => setRoom(r.id)}
              >
                {r.name}
                <span className={r.fits ? styles.chipNote : styles.chipWarn}> · {r.capacity}</span>
              </button>
            ))}
            <button
              type="button"
              className={styles.chip}
              aria-pressed={room === ""}
              onClick={() => setRoom("")}
            >
              {t("schedule.noRoom")}
            </button>
          </div>
        </Step>
      )}

      {timed && room !== null && (
        <Step n={6 + shift} title={t("schedule.stepFinish")}>
          <SelectField
            label={t("schedule.lessonType")}
            value={lessonType}
            onChange={(e) => setLessonType(e.target.value)}
            options={[
              { value: "", label: "—" },
              ...(lessonTypes.data ?? [])
                .filter((x) => !x.is_archived)
                .map((x) => ({ value: x.id, label: x.name })),
            ]}
          />
        </Step>
      )}

      <ScheduleIssues conflicts={conflicts} />
      {save.error && !conflicts.length && (
        <p className={styles.error} role="alert">
          {fieldsError
            ? fieldError(save.error, "end_time") || errorMessage(save.error)
            : errorMessage(save.error)}
        </p>
      )}
      <DialogActions>
        <Button
          type="submit"
          variant="primary"
          disabled={!timed || room === null || save.isPending}
        >
          {mode === "lesson" ? t("schedule.addLesson") : t("schedule.addSlot")}
        </Button>
        <Button onClick={onCancel}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <fieldset className={styles.step}>
      <legend className={styles.stepTitle}>
        <span className={styles.stepNumber}>{n}</span>
        {title}
      </legend>
      {children}
    </fieldset>
  );
}
