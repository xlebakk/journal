import { AlertTriangle } from "lucide-react";

import { t, type MessageKey } from "@/shared/i18n";
import { formatDayLong, weekdayNames } from "@/shared/lib/week";

import styles from "./ScheduleIssues.module.css";

export type ScheduleConflict = {
  kind: "teacher" | "room" | "group";
  date?: string;
  at?: string;
  weekday?: number;
  start_time: string;
  end_time: string;
  group: string;
  subject: string;
  teacher: string;
  room: string | null;
};

export type ScheduleWarning =
  | { kind: "students"; date: string; students: string[] }
  | { kind: "capacity"; date: string; room: string; capacity: number; students: number };

const KIND: Record<ScheduleConflict["kind"], MessageKey> = {
  teacher: "schedule.conflictTeacher",
  room: "schedule.conflictRoom",
  group: "schedule.conflictGroup",
};

function when(conflict: ScheduleConflict): string {
  const day = conflict.at ?? conflict.date;
  const label = day
    ? formatDayLong(day)
    : conflict.weekday
      ? (weekdayNames()[conflict.weekday - 1] ?? "")
      : "";
  return `${label} ${conflict.start_time}–${conflict.end_time}`;
}

/** Hard conflicts (not saved) and warnings (saved), in words (SPEC §9). */
export function ScheduleIssues({
  conflicts = [],
  warnings = [],
}: {
  conflicts?: ScheduleConflict[];
  warnings?: ScheduleWarning[];
}) {
  if (!conflicts.length && !warnings.length) return null;
  return (
    <div className={styles.issues}>
      {conflicts.length > 0 && (
        <div role="alert">
          <p className={styles.title}>
            <AlertTriangle size={16} strokeWidth={1.5} aria-hidden="true" />{" "}
            {t("schedule.conflictsTitle")}
          </p>
          <ul className={styles.list}>
            {conflicts.map((c, i) => (
              <li key={i} className={styles.conflict}>
                {t(KIND[c.kind])}: <span className="mono">{when(c)}</span> · {c.group} · {c.subject}{" "}
                · {c.teacher}
                {c.room && <> · {t("schedule.room", { room: c.room })}</>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {warnings.length > 0 && (
        <div role="status">
          <p className={styles.title}>{t("schedule.warningsTitle")}</p>
          <ul className={styles.list}>
            {warnings.map((w, i) => (
              <li key={i} className={styles.warning}>
                {w.kind === "students"
                  ? t("schedule.warningStudents", {
                      date: formatDayLong(w.date),
                      names: w.students.join(", "),
                    })
                  : t("schedule.warningCapacity", {
                      date: formatDayLong(w.date),
                      room: w.room,
                      capacity: w.capacity,
                      students: w.students,
                    })}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
