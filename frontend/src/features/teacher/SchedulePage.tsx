import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import {
  useInvalidateSchedule,
  useRooms,
  useTeacherRequests,
  useTeacherSchedule,
  useWeekParam,
  type Lesson,
  type ScheduleRequest,
} from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { requestSummary } from "./requestSummary";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";
import {
  Button,
  Dialog,
  DialogActions,
  EmptyState,
  lessonMarks,
  RuledSkeleton,
  SelectField,
  Table,
  TextField,
  DaySchedule,
  PeriodBar,
  Segmented,
} from "@/shared/ui";

function LessonFacts({ lesson }: { lesson: Lesson }) {
  return (
    <dl className={styles.facts}>
      <dt>{t("schedule.date")}</dt>
      <dd>
        {formatDayLong(lesson.date)},{" "}
        <span className="mono">
          {hhmm(lesson.start_time)}–{hhmm(lesson.end_time)}
        </span>
      </dd>
      <dt>{t("schedule.group")}</dt>
      <dd>{lesson.group_name}</dd>
      <dt>{t("schedule.roomFilter")}</dt>
      <dd>{lesson.room_name ?? t("schedule.noRoom")}</dd>
      <dt>{t("schedule.teacher")}</dt>
      <dd>{lesson.teacher_name}</dd>
      {lessonMarks(lesson).map((mark) => (
        <dd key={mark.text}>{mark.text}</dd>
      ))}
    </dl>
  );
}

/** Ask the administrator to cancel or move one of the teacher's lessons (SPEC §9). */
function RequestForm({ lesson, onDone }: { lesson: Lesson; onDone: () => void }) {
  const rooms = useRooms();
  const invalidate = useInvalidateSchedule();
  const [kind, setKind] = useState<"cancel" | "move">("cancel");
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(lesson.date);
  const [start, setStart] = useState(hhmm(lesson.start_time));
  const [end, setEnd] = useState(hhmm(lesson.end_time));
  const [room, setRoom] = useState("");
  const send = useMutation({
    mutationFn: () =>
      api<ScheduleRequest>(`/teacher/lessons/${lesson.id}/requests`, {
        method: "POST",
        body:
          kind === "cancel"
            ? { kind, reason }
            : {
                kind,
                reason,
                proposed_date: date,
                proposed_start_time: start,
                proposed_end_time: end,
                proposed_room: room || null,
              },
      }),
    onSuccess: async () => {
      await invalidate();
      onDone();
    },
  });
  const editable = lesson.status === "planned";
  if (!editable) return null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    send.mutate();
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <div className={styles.tabs} role="tablist">
        {(["cancel", "move"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={kind === value}
            className={styles.tab}
            onClick={() => setKind(value)}
          >
            {t(value === "cancel" ? "schedule.requestCancel" : "schedule.requestMove")}
          </button>
        ))}
      </div>
      {kind === "move" && (
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
          />
          <SelectField
            label={t("schedule.roomFilter")}
            value={room}
            onChange={(e) => setRoom(e.target.value)}
            options={[
              { value: "", label: lesson.room_name ?? t("schedule.noRoom") },
              ...(rooms.data ?? []).map((r) => ({ value: r.id, label: r.name })),
            ]}
          />
        </div>
      )}
      <TextField
        label={t("schedule.requestReason")}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        error={fieldError(send.error, "reason")}
        required
      />
      {send.error && !fieldError(send.error, "reason") && (
        <p className={styles.error} role="alert">
          {errorMessage(send.error)}
        </p>
      )}
      <DialogActions>
        <Button type="submit" variant="primary" disabled={send.isPending || !reason.trim()}>
          {t(kind === "cancel" ? "schedule.requestCancel" : "schedule.requestMove")}
        </Button>
        <Button onClick={onDone}>{t("common.cancel")}</Button>
      </DialogActions>
    </form>
  );
}

const REQUEST_STATUS: Record<string, MessageKey> = {
  pending: "schedule.requestPending",
  approved: "schedule.requestApproved",
  rejected: "schedule.requestRejected",
  withdrawn: "schedule.requestWithdrawn",
};

function MyRequests() {
  const requests = useTeacherRequests();
  const invalidate = useInvalidateSchedule();
  const withdraw = useMutation({
    mutationFn: (id: string) =>
      api(`/teacher/schedule-requests/${id}/withdraw`, { method: "POST" }),
    onSuccess: () => invalidate(),
  });
  if (requests.isPending) return <RuledSkeleton rows={2} />;
  const items = requests.data ?? [];
  return (
    <section className={styles.section} aria-labelledby="my-requests">
      <h2 id="my-requests" className="visually-hidden">
        {t("schedule.myRequests")}
      </h2>
      {items.length === 0 ? (
        <EmptyState text={t("schedule.requestsEmpty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("schedule.lessonTitle")}</th>
              <th scope="col">{t("schedule.requestReason")}</th>
              <th scope="col">{t("schedule.status")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("schedule.withdraw")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.id}>
                <td>
                  {r.lesson_info.subject_name} · {r.lesson_info.group_name},{" "}
                  {formatDayLong(r.lesson_info.planned_date)} — {requestSummary(r)}
                </td>
                <td>{r.reason}</td>
                <td>
                  {t(REQUEST_STATUS[r.status] ?? "schedule.requestPending")}
                  {r.resolution_comment && (
                    <span className={styles.status}> · {r.resolution_comment}</span>
                  )}
                </td>
                <td>
                  {r.status === "pending" && (
                    <Button onClick={() => withdraw.mutate(r.id)} disabled={withdraw.isPending}>
                      {t("schedule.withdraw")}
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </section>
  );
}

/** «Расписание» of a teacher: own courses, assisted courses, substitutions (SPEC §7.5). */
export function SchedulePage() {
  const [monday, setMonday, today] = useWeekParam();
  const schedule = useTeacherSchedule(monday);
  const [selected, setSelected] = useState<Lesson | null>(null);
  const [sent, setSent] = useState(false);
  const lessons = schedule.data ?? [];
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "requests" ? "requests" : "week";
  const pending = useTeacherRequests().data?.filter((r) => r.status === "pending").length ?? 0;
  const setView = (next: "week" | "requests") => {
    const changed = new URLSearchParams(params);
    if (next === "requests") changed.set("view", next);
    else changed.delete("view");
    setParams(changed, { replace: true });
  };

  return (
    <section className={styles.page}>
      <h1 className="visually-hidden">{t("schedule.title")}</h1>
      <Segmented
        label={t("schedule.title")}
        value={view}
        onChange={setView}
        options={[
          { value: "week", label: t("schedule.mySchedule") },
          {
            value: "requests",
            label: pending
              ? t("schedule.myRequestsCount", { count: pending })
              : t("schedule.myRequests"),
          },
        ]}
      />
      {view === "requests" ? (
        <MyRequests />
      ) : (
        <>
          <PeriodBar monday={monday} today={today} onChange={setMonday} />
          {sent && (
            <p className={styles.success} role="status">
              {t("schedule.requestSent")}
            </p>
          )}
          {schedule.isPending ? (
            <RuledSkeleton rows={6} />
          ) : schedule.error ? (
            <p className={styles.error}>{errorMessage(schedule.error)}</p>
          ) : (
            <DaySchedule
              monday={monday}
              today={today}
              lessons={lessons}
              showGroup
              onSelect={(item) => setSelected(lessons.find((l) => l.id === item.id) ?? null)}
            />
          )}
        </>
      )}
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? selected.subject_name : t("schedule.lessonTitle")}
      >
        {selected && (
          <>
            <LessonFacts lesson={selected} />
            {selected.date >= today && (
              <RequestForm
                lesson={selected}
                onDone={() => {
                  setSelected(null);
                  setSent(true);
                }}
              />
            )}
          </>
        )}
      </Dialog>
    </section>
  );
}
