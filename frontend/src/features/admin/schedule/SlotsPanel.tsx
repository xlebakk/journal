import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useCourses } from "@/features/admin/groups/api";
import { useInvalidateSchedule, useRooms, type Slot } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate, hhmm, weekdayNames } from "@/shared/lib/week";
import {
  Button,
  Dialog,
  DialogActions,
  EmptyState,
  RuledSkeleton,
  ScheduleIssues,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { issuesOf, useLessonTypes, useSlots, warningsOf, type Filters, type Plan } from "./api";
import { LessonWizard } from "./LessonWizard";

type Values = {
  course: string;
  weekday: string;
  start_time: string;
  end_time: string;
  room: string;
  lesson_type: string;
  valid_from: string;
  valid_to: string;
};

function initial(slot: Slot | null, today: string): Values {
  return {
    course: slot?.course ?? "",
    weekday: String(slot?.weekday ?? 1),
    start_time: hhmm(slot?.start_time) || "16:00",
    end_time: hhmm(slot?.end_time) || "17:30",
    room: slot?.room ?? "",
    lesson_type: slot?.lesson_type ?? "",
    valid_from: slot?.valid_from ?? today,
    valid_to: slot?.valid_to ?? "",
  };
}

function body(values: Values, create: boolean) {
  return {
    ...(create ? { course: values.course } : {}),
    weekday: Number(values.weekday),
    start_time: values.start_time,
    end_time: values.end_time,
    room: values.room || null,
    lesson_type: values.lesson_type || null,
    valid_from: values.valid_from,
    valid_to: values.valid_to || null,
  };
}

/** The list of dates a template change touches, to confirm. */
function PlanSummary({ plan }: { plan: Plan }) {
  const rows: [string, string[]][] = [
    [t("schedule.planUpdated"), plan.updated],
    [t("schedule.planRemoved"), plan.removed],
    [t("schedule.planAdded"), plan.added],
    [t("schedule.planKept"), plan.kept_exceptions],
  ];
  return (
    <dl className={styles.facts}>
      {rows
        .filter(([, dates]) => dates.length > 0)
        .map(([label, dates]) => (
          <div key={label} className={styles.section}>
            <dt>{label}</dt>
            <dd className="mono">{dates.map(formatDate).join(", ")}</dd>
          </div>
        ))}
    </dl>
  );
}

function SlotForm({
  slot,
  today,
  onDone,
}: {
  slot: Slot | null;
  today: string;
  onDone: (warnings: ScheduleWarning[]) => void;
}) {
  const courses = useCourses();
  const rooms = useRooms();
  const lessonTypes = useLessonTypes();
  const invalidate = useInvalidateSchedule();
  const [values, setValues] = useState(() => initial(slot, today));
  const [plan, setPlan] = useState<Plan | null>(null);
  const set = (name: keyof Values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [name]: e.target.value }));

  const save = useMutation({
    mutationFn: async (confirm: boolean) => {
      if (!slot) return api<unknown>("/admin/slots", { method: "POST", body: body(values, true) });
      if (!confirm) {
        // Preview first: show which dates change before anything is saved.
        const preview = await api<{ plan: Plan }>(`/admin/slots/${slot.id}/preview`, {
          method: "POST",
          body: body(values, false),
        });
        if (preview.plan.updated.length || preview.plan.removed.length) {
          setPlan(preview.plan);
          return null;
        }
      }
      return api<unknown>(`/admin/slots/${slot.id}`, {
        method: "PATCH",
        body: { ...body(values, false), confirm: true },
      });
    },
    onSuccess: async (data) => {
      if (data === null) return;
      await invalidate();
      onDone(warningsOf(data));
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate(plan !== null);
  };
  const { conflicts } = issuesOf(save.error);
  const fieldsError = save.error instanceof ApiError && Object.keys(save.error.fields).length > 0;

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      {plan ? (
        <>
          <p className={styles.note}>{t("schedule.confirmNote")}</p>
          <PlanSummary plan={plan} />
        </>
      ) : (
        <>
          <p className={styles.note}>{t("schedule.templateNote")}</p>
          {!slot && (
            <SelectField
              label={t("schedule.course")}
              value={values.course}
              onChange={set("course")}
              options={[
                { value: "", label: "—" },
                ...(courses.data ?? []).map((c) => ({
                  value: c.id,
                  label: `${c.group_name} · ${c.subject_name} · ${c.teacher_info.short_name}`,
                })),
              ]}
              error={fieldError(save.error, "course")}
            />
          )}
          <div className={styles.grid}>
            <SelectField
              label={t("schedule.weekday")}
              value={values.weekday}
              onChange={set("weekday")}
              options={weekdayNames().map((name, i) => ({ value: String(i + 1), label: name }))}
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
              error={fieldError(save.error, "end_time")}
            />
            <SelectField
              label={t("schedule.roomFilter")}
              value={values.room}
              onChange={set("room")}
              options={[
                { value: "", label: t("schedule.noRoom") },
                ...(rooms.data ?? []).map((r) => ({
                  value: r.id,
                  label: `${r.name} (${r.capacity})`,
                })),
              ]}
            />
            <SelectField
              label={t("schedule.lessonType")}
              value={values.lesson_type}
              onChange={set("lesson_type")}
              options={[
                { value: "", label: "—" },
                ...(lessonTypes.data ?? [])
                  .filter((x) => !x.is_archived)
                  .map((x) => ({ value: x.id, label: x.name })),
              ]}
            />
            <TextField
              label={t("schedule.validFrom")}
              type="date"
              value={values.valid_from}
              onChange={set("valid_from")}
            />
            <TextField
              label={t("schedule.validTo")}
              type="date"
              hint={t("schedule.validToHint")}
              value={values.valid_to}
              onChange={set("valid_to")}
              error={fieldError(save.error, "valid_to")}
            />
          </div>
        </>
      )}
      <ScheduleIssues conflicts={conflicts} />
      {save.error && !conflicts.length && !fieldsError && (
        <p className={styles.error} role="alert">
          {errorMessage(save.error)}
        </p>
      )}
      <DialogActions>
        <Button
          type="submit"
          variant="primary"
          disabled={save.isPending || (!slot && !values.course)}
        >
          {plan ? t("schedule.confirm") : t("schedule.save")}
        </Button>
        {plan && <Button onClick={() => setPlan(null)}>{t("common.back")}</Button>}
      </DialogActions>
    </form>
  );
}

function DeleteSlot({ slot, onDone }: { slot: Slot; onDone: () => void }) {
  const invalidate = useInvalidateSchedule();
  const [plan, setPlan] = useState<Plan | null>(null);
  const remove = useMutation({
    mutationFn: async () => {
      try {
        return await api(`/admin/slots/${slot.id}`, {
          method: "DELETE",
          query: plan ? { confirm: "true" } : undefined,
        });
      } catch (error) {
        const found = issuesOf(error).plan;
        if (found && !plan) {
          setPlan(found);
          return null;
        }
        throw error;
      }
    },
    onSuccess: async (data) => {
      if (data === null) return;
      await invalidate();
      onDone();
    },
  });
  return (
    <div className={styles.form}>
      <p className={styles.note}>
        {slot.group_name} · {slot.subject_name}, {weekdayNames()[slot.weekday - 1]}{" "}
        {hhmm(slot.start_time)}
      </p>
      {plan && (
        <>
          <p className={styles.note}>{t("schedule.confirmNote")}</p>
          <PlanSummary plan={plan} />
        </>
      )}
      {remove.error && (
        <p className={styles.error} role="alert">
          {errorMessage(remove.error)}
        </p>
      )}
      <DialogActions>
        <Button variant="primary" onClick={() => remove.mutate()} disabled={remove.isPending}>
          {plan ? t("schedule.confirm") : t("schedule.delete")}
        </Button>
        <Button onClick={onDone}>{t("common.cancel")}</Button>
      </DialogActions>
    </div>
  );
}

/** «Шаблон недели»: slots by weekday. */
export function SlotsPanel({
  filters,
  today,
  onWarnings,
}: {
  filters: Filters;
  today: string;
  onWarnings: (warnings: ScheduleWarning[]) => void;
}) {
  const slots = useSlots(filters);
  const [dialog, setDialog] = useState<
    { kind: "edit"; slot: Slot | null } | { kind: "delete"; slot: Slot } | null
  >(null);
  const close = () => setDialog(null);
  return (
    <section className={styles.section}>
      <div className={styles.row}>
        <Button onClick={() => setDialog({ kind: "edit", slot: null })}>
          {t("schedule.addSlot")}
        </Button>
      </div>
      {slots.isPending ? (
        <RuledSkeleton rows={5} />
      ) : slots.error ? (
        <p className={styles.error}>{errorMessage(slots.error)}</p>
      ) : slots.data.length === 0 ? (
        <EmptyState text={t("schedule.templateEmpty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("schedule.weekday")}</th>
              <th scope="col">{t("schedule.start")}</th>
              <th scope="col">{t("schedule.group")}</th>
              <th scope="col">{t("groups.subject")}</th>
              <th scope="col">{t("schedule.teacher")}</th>
              <th scope="col">{t("schedule.roomFilter")}</th>
              <th scope="col">{t("schedule.validFrom")}</th>
              <th scope="col">
                <span className="visually-hidden">{t("catalogs.edit")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {slots.data.map((slot) => (
              <tr key={slot.id}>
                <td>{weekdayNames()[slot.weekday - 1]}</td>
                <td className="mono">
                  {hhmm(slot.start_time)}–{hhmm(slot.end_time)}
                </td>
                <td>{slot.group_name}</td>
                <td>
                  {slot.subject_name}
                  {slot.lesson_type_short && (
                    <span className={styles.status}> · {slot.lesson_type_short}</span>
                  )}
                </td>
                <td>{slot.teacher_name}</td>
                <td>{slot.room_name ?? "—"}</td>
                <td className="mono">
                  {formatDate(slot.valid_from)}
                  {slot.valid_to && <> – {formatDate(slot.valid_to)}</>}
                </td>
                <td>
                  <span className={styles.row}>
                    <Button onClick={() => setDialog({ kind: "edit", slot })}>
                      {t("catalogs.edit")}
                    </Button>
                    <Button variant="danger" onClick={() => setDialog({ kind: "delete", slot })}>
                      {t("catalogs.delete")}
                    </Button>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <Dialog
        open={dialog !== null}
        onOpenChange={(o) => !o && close()}
        title={
          dialog?.kind === "delete"
            ? t("schedule.delete")
            : dialog?.slot
              ? `${dialog.slot.group_name} · ${dialog.slot.subject_name}`
              : t("schedule.addSlot")
        }
      >
        {dialog?.kind === "edit" && !dialog.slot && (
          // A new slot is built step by step from what is free (stage 19).
          <LessonWizard
            mode="slot"
            today={today}
            presetGroup={filters.group}
            onDone={(warnings) => {
              close();
              onWarnings(warnings);
            }}
            onCancel={close}
          />
        )}
        {dialog?.kind === "edit" && dialog.slot && (
          <SlotForm
            slot={dialog.slot}
            today={today}
            onDone={(warnings) => {
              close();
              onWarnings(warnings);
            }}
          />
        )}
        {dialog?.kind === "delete" && <DeleteSlot slot={dialog.slot} onDone={close} />}
      </Dialog>
    </section>
  );
}
