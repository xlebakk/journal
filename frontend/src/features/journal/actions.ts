import { t, type MessageKey } from "@/shared/i18n";

import { journalApi, type Attendance, type AttendanceStatus, type Grade } from "./api";
import { dequeue, rememberVersion, versionOf } from "./offlineQueue";
import {
  isPendingId,
  patchAllPresent,
  patchAttendance,
  patchGradeAdd,
  patchGradeRemove,
  patchLesson,
  PENDING,
} from "./offlinePatches";
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
// Б / О / Н / У on a Russian layout, the same physical keys on a Latin one;
// «a» for the English «absent»; KeyY is the physical key of «н».
const KEYS: Record<string, AttendanceStatus> = {
  б: "present",
  н: "absent",
  a: "absent", // English: «a» for absent
  // Stage 19: lateness and excused absences are switched off for now.
  // о: "late",
  // у: "excused",
  // k: "late",
  // s: "excused",
};
const CODES: Record<string, AttendanceStatus> = {
  Comma: "present",
  KeyY: "absent",
  // KeyJ: "late",
  // KeyE: "excused",
};

export function statusFromKey(event: { key: string; code: string }): AttendanceStatus | undefined {
  return KEYS[event.key.toLowerCase()] ?? CODES[event.code];
}

/** Version 0 marks a row only the screen has (queued, not yet on the server). */
function known(version: number | undefined): number | null {
  return version ? version : null;
}

async function currentAttendance(lessonId: string, studentId: string) {
  const page = await journalApi.lessonPage(lessonId);
  return page.attendance.find((a) => a.student === studentId);
}

export function attendanceAction(
  lesson: LessonRef,
  studentId: string,
  previous: Attendance | undefined,
  changes: { status: AttendanceStatus; late_minutes?: number | null; comment?: string },
  reason: string,
  who = "",
): Action {
  const key = `attendance:${lesson.id}:${studentId}`;
  const send = (version: number | null) =>
    journalApi
      .setAttendance(lesson.id, studentId, { ...changes, version, reason })
      .then((saved) => {
        rememberVersion(key, saved.version);
        return saved;
      });
  return {
    run: () => send(versionOf(key, known(previous?.version))),
    undo: (result) => {
      const saved = result as Attendance;
      return previous && previous.version
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
    offline: {
      key,
      label: `${who} · ${t(STATUS_NAME[changes.status])}`,
      patch: patchAttendance(lesson.id, studentId, changes),
      force: async () => send(known((await currentAttendance(lesson.id, studentId))?.version)),
      alreadyThere: async () => {
        const current = await currentAttendance(lesson.id, studentId);
        if (!current || current.status !== changes.status) return false;
        rememberVersion(key, current.version);
        return true;
      },
    },
  };
}

export function allPresentAction(lessonId: string, reason: string): Action {
  return {
    run: () =>
      journalApi.allPresent(lessonId, { reason }).then((marks) => {
        for (const mark of marks) {
          rememberVersion(`attendance:${lessonId}:${mark.student}`, mark.version);
        }
        return marks;
      }),
    offline: {
      key: `all-present:${lessonId}`,
      label: t("journal.allPresent"),
      patch: patchAllPresent(lessonId),
    },
  };
}

export function addGradeAction(
  lesson: LessonRef,
  studentId: string,
  value: number,
  reason: string,
  workType?: string,
  who = "",
  comment = "",
): Action {
  // The same key goes with every resend: the server creates the grade once (stage 13).
  const clientKey = crypto.randomUUID();
  const key = `grade:${clientKey}`;
  return {
    run: () =>
      journalApi.addGrade(lesson.id, {
        student: studentId,
        value,
        work_type: workType ?? null,
        ...(comment ? { comment } : {}),
        reason,
        client_key: clientKey,
      }),
    undo: (result) => {
      const grade = result as Grade;
      return () => journalApi.deleteGrade(grade.id, { version: grade.version, reason });
    },
    offline: {
      key,
      label: `${who} · ${value}`,
      patch: patchGradeAdd(lesson.id, studentId, value, workType ?? null, key),
    },
  };
}

export function deleteGradeAction(grade: Grade, reason: string): Action {
  if (isPendingId(grade.id)) {
    // Not on the server yet: take it out of the queue, nothing to send.
    const key = grade.id.slice(PENDING.length);
    return {
      run: async () => dequeue(key),
      localPatch: patchGradeRemove(grade.id),
    };
  }
  return {
    run: () => journalApi.deleteGrade(grade.id, { version: grade.version, reason }),
    undo: (result) => () =>
      journalApi.restoreGrade(grade.id, { version: (result as Grade).version, reason }),
  };
}

/** A new value or remark of one's own grade (the cell window, stage 18); needs the network. */
export function updateGradeAction(
  grade: Grade,
  changes: { value: number; comment: string },
  reason: string,
): Action {
  return {
    run: () => journalApi.updateGrade(grade.id, { version: grade.version, ...changes, reason }),
    undo: (result) => () =>
      journalApi.updateGrade(grade.id, {
        version: (result as Grade).version,
        value: grade.value,
        comment: grade.comment,
        reason,
      }),
  };
}

/** Topic, homework, lesson type or comment of a lesson; each field waits on its own. */
export function lessonAction(
  lesson: { id: string; version: number },
  changes: Record<string, unknown>,
  reason: string,
  label: string,
): Action {
  const key = `lesson:${lesson.id}`;
  const send = (version: number) =>
    journalApi.updateLesson(lesson.id, { version, reason, ...changes }).then((page) => {
      rememberVersion(key, page.lesson.version);
      return page;
    });
  return {
    run: () => send(versionOf(key, lesson.version) ?? lesson.version),
    offline: {
      key: `${key}:${Object.keys(changes).sort().join(",")}`,
      label,
      patch: patchLesson(lesson.id, changes),
      force: async () => send((await journalApi.lessonPage(lesson.id)).lesson.version),
    },
  };
}
