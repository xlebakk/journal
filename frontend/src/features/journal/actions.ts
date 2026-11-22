import { t, type MessageKey } from "@/shared/i18n";

import { journalApi, type Attendance, type AttendanceStatus, type Grade } from "./api";
import type { Action } from "./useSave";

export type LessonRef = { id: string; editable: boolean; needs_reason: boolean };

const MARK_KEY: Record<AttendanceStatus, MessageKey> = {
  present: "attendance.present",
  late: "attendance.lateShort",
  absent: "attendance.absentShort",
  excused: "attendance.excusedShort",
};

/** «был», «оп», «н», «у» — in the interface language. */
export function mark(status: AttendanceStatus): string {
  return t(MARK_KEY[status]);
}
export const STATUS_NAME: Record<AttendanceStatus, MessageKey> = {
  present: "attendance.present",
  late: "attendance.late",
  absent: "attendance.absent",
  excused: "attendance.excused",
};
// Б / О / Н / У on a Russian layout, the same physical keys on a Latin one (SPEC §7.2);
// K / S for the Uzbek «kechikdi» and «sababli» («y» for «yoʻq» is the key of «н»).
const KEYS: Record<string, AttendanceStatus> = {
  б: "present",
  о: "late",
  н: "absent",
  у: "excused",
  k: "late",
  s: "excused",
};
const CODES: Record<string, AttendanceStatus> = {
  Comma: "present",
  KeyJ: "late",
  KeyY: "absent",
  KeyE: "excused",
};

export function statusFromKey(event: { key: string; code: string }): AttendanceStatus | undefined {
  return KEYS[event.key.toLowerCase()] ?? CODES[event.code];
}

export function attendanceAction(
  lesson: LessonRef,
  studentId: string,
  previous: Attendance | undefined,
  changes: { status: AttendanceStatus; late_minutes?: number | null; comment?: string },
  reason: string,
): Action {
  return {
    run: () =>
      journalApi.setAttendance(lesson.id, studentId, {
        ...changes,
        version: previous?.version ?? null,
        reason,
      }),
    undo: (result) => {
      const saved = result as Attendance;
      return previous
        ? () =>
            journalApi.setAttendance(lesson.id, studentId, {
              status: previous.status,
              late_minutes: previous.late_minutes,
              comment: previous.comment,
              version: saved.version,
              reason,
            })
        : () =>
            journalApi.clearAttendance(lesson.id, studentId, { version: saved.version, reason });
    },
  };
}

export function addGradeAction(
  lesson: LessonRef,
  studentId: string,
  value: number,
  reason: string,
  workType?: string,
): Action {
  return {
    run: () =>
      journalApi.addGrade(lesson.id, {
        student: studentId,
        value,
        work_type: workType ?? null,
        reason,
      }),
    undo: (result) => {
      const grade = result as Grade;
      return () => journalApi.deleteGrade(grade.id, { version: grade.version, reason });
    },
  };
}

export function deleteGradeAction(grade: Grade, reason: string): Action {
  return {
    run: () => journalApi.deleteGrade(grade.id, { version: grade.version, reason }),
    undo: (result) => () =>
      journalApi.restoreGrade(grade.id, { version: (result as Grade).version, reason }),
  };
}
