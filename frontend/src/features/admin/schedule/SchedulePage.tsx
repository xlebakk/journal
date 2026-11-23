import { useState } from "react";
import { useSearchParams } from "react-router";

import { useGroups, useTeachers } from "@/features/admin/groups/api";
import { useRooms, useWeekParam, type Lesson } from "@/features/schedule/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { canPrint } from "@/platform";
import { t } from "@/shared/i18n";
import { startOfWeek } from "@/shared/lib/week";
import {
  Button,
  RuledSkeleton,
  ScheduleIssues,
  SelectField,
  WeekNav,
  WeekSchedule,
} from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { useAdminLessons, type Filters } from "./api";
import { ExtraLessonDialog, type AddAt } from "./ExtraLessonDialog";
import { LessonDialog } from "./LessonDialog";
import { SlotsPanel } from "./SlotsPanel";

/** Schedule builder for administrators: the week and its template. */
export function SchedulePage() {
  const [params, setParams] = useSearchParams();
  const [monday, setMonday, today] = useWeekParam();
  const mode = params.get("mode") === "template" ? "template" : "week";
  const filters: Filters = {
    group: params.get("group") || undefined,
    teacher: params.get("teacher") || undefined,
    room: params.get("room") || undefined,
  };
  const groups = useGroups();
  const teachers = useTeachers();
  const rooms = useRooms();
  const lessons = useAdminLessons(monday, filters);
  const [selected, setSelected] = useState<Lesson | null>(null);
  const [adding, setAdding] = useState<AddAt | null>(null);
  const [warnings, setWarnings] = useState<ScheduleWarning[]>([]);

  const setParam = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next, { replace: true });
  };
  const groupName = groups.data?.find((g) => g.id === filters.group)?.name;
  const data = lessons.data ?? [];

  return (
    <section className={styles.page}>
      <h1 className={styles.printHeader}>
        {groupName ? t("schedule.printTitle", { group: groupName }) : t("schedule.title")}
      </h1>
      <div className={`${styles.titleRow} ${styles.noPrint}`}>
        <h1>{t("schedule.title")}</h1>
        {mode === "week" && (
          <WeekNav
            monday={monday}
            onChange={setMonday}
            onToday={() => setMonday(startOfWeek(today))}
          />
        )}
      </div>

      <div className={`${styles.tabs} ${styles.noPrint}`} role="tablist">
        {(
          [
            ["week", "schedule.week"],
            ["template", "schedule.template"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            className={styles.tab}
            onClick={() => setParam("mode", value === "week" ? "" : value)}
          >
            {t(label)}
          </button>
        ))}
      </div>

      <div className={`${styles.toolbar} ${styles.noPrint}`}>
        <SelectField
          label={t("schedule.group")}
          value={filters.group ?? ""}
          onChange={(e) => setParam("group", e.target.value)}
          options={[
            { value: "", label: t("schedule.any") },
            ...(groups.data ?? []).map((g) => ({ value: g.id, label: g.name })),
          ]}
        />
        <SelectField
          label={t("schedule.teacher")}
          value={filters.teacher ?? ""}
          onChange={(e) => setParam("teacher", e.target.value)}
          options={[
            { value: "", label: t("schedule.any") },
            ...(teachers.data ?? []).map((p) => ({ value: p.id, label: p.short_name })),
          ]}
        />
        <SelectField
          label={t("schedule.roomFilter")}
          value={filters.room ?? ""}
          onChange={(e) => setParam("room", e.target.value)}
          options={[
            { value: "", label: t("schedule.any") },
            ...(rooms.data ?? []).map((r) => ({ value: r.id, label: r.name })),
          ]}
        />
        {mode === "week" && (
          <>
            <Button onClick={() => setAdding({ group: filters.group })}>
              {t("schedule.addLesson")}
            </Button>
            {canPrint && <Button onClick={() => window.print()}>{t("schedule.print")}</Button>}
          </>
        )}
      </div>

      <div className={styles.noPrint}>
        <ScheduleIssues warnings={warnings} />
      </div>

      {mode === "template" ? (
        <SlotsPanel filters={filters} today={today} onWarnings={setWarnings} />
      ) : lessons.isPending ? (
        <RuledSkeleton rows={8} />
      ) : lessons.error ? (
        <p className={styles.error}>{errorMessage(lessons.error)}</p>
      ) : (
        <WeekSchedule
          monday={monday}
          today={today}
          lessons={data}
          showGroup={!filters.group}
          showTeacher
          onSelect={(item) => setSelected(data.find((l) => l.id === item.id) ?? null)}
          onAddAt={(date, time) => setAdding({ date, time, group: filters.group })}
        />
      )}

      <LessonDialog
        lesson={selected ? (data.find((l) => l.id === selected.id) ?? selected) : null}
        onClose={() => setSelected(null)}
      />
      <ExtraLessonDialog
        at={adding}
        today={today}
        onClose={(found) => {
          setAdding(null);
          setWarnings(found);
        }}
      />
    </section>
  );
}
