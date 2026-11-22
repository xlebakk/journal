/**
 * How a queued change shows in the cached journal data before the server has it (stage 13).
 * The lesson page and the grid both keep `attendance` and `grades` arrays; a patch touches a
 * cache only if it holds that lesson. Version 0 marks a row the server does not have yet.
 */
import type { Attendance, AttendanceStatus, Grade } from "./api";

type Journalish = {
  lesson?: { id: string; topic?: string; homework?: string; lesson_type?: string | null };
  lessons?: { id: string; topic?: string }[];
  students?: { id: string }[];
  attendance?: Attendance[];
  grades?: Grade[];
  comment?: string;
};

function holds(data: Journalish, lessonId: string): boolean {
  return data.lesson?.id === lessonId || Boolean(data.lessons?.some((l) => l.id === lessonId));
}

export const PENDING = "pending-";

export function patchAttendance(
  lessonId: string,
  studentId: string,
  changes: { status: AttendanceStatus; late_minutes?: number | null; comment?: string },
) {
  return (raw: unknown): unknown => {
    const data = raw as Journalish;
    if (!Array.isArray(data.attendance) || !holds(data, lessonId)) return raw;
    const existing = data.attendance.find((a) => a.lesson === lessonId && a.student === studentId);
    const next: Attendance = existing
      ? { ...existing, ...changes }
      : {
          id: `${PENDING}${lessonId}-${studentId}`,
          lesson: lessonId,
          student: studentId,
          status: changes.status,
          late_minutes: changes.late_minutes ?? null,
          comment: changes.comment ?? "",
          version: 0,
        };
    const attendance = existing
      ? data.attendance.map((a) => (a === existing ? next : a))
      : [...data.attendance, next];
    return { ...data, attendance };
  };
}

export function patchAllPresent(lessonId: string) {
  return (raw: unknown): unknown => {
    const data = raw as Journalish;
    if (!Array.isArray(data.attendance) || data.lesson?.id !== lessonId || !data.students) {
      return raw;
    }
    const marked = new Set(data.attendance.map((a) => a.student));
    const added: Attendance[] = data.students
      .filter((s) => !marked.has(s.id))
      .map((s) => ({
        id: `${PENDING}${lessonId}-${s.id}`,
        lesson: lessonId,
        student: s.id,
        status: "present",
        late_minutes: null,
        comment: "",
        version: 0,
      }));
    return { ...data, attendance: [...data.attendance, ...added] };
  };
}

export function patchGradeAdd(
  lessonId: string,
  studentId: string,
  value: number,
  workType: string | null,
  key: string,
) {
  return (raw: unknown): unknown => {
    const data = raw as Journalish;
    if (!Array.isArray(data.grades) || !holds(data, lessonId)) return raw;
    const own = data.grades.filter((g) => g.lesson === lessonId && g.student === studentId);
    const grade: Grade = {
      id: `${PENDING}${key}`,
      lesson: lessonId,
      student: studentId,
      value,
      work_type: workType ?? "",
      weight: "1.00",
      comment: "",
      position: own.length + 1,
      mine: true,
      author_name: "",
      version: 0,
    };
    return { ...data, grades: [...data.grades, grade] };
  };
}

export function patchGradeRemove(gradeId: string) {
  return (raw: unknown): unknown => {
    const data = raw as Journalish;
    if (!Array.isArray(data.grades)) return raw;
    return { ...data, grades: data.grades.filter((g) => g.id !== gradeId) };
  };
}

export function patchLesson(lessonId: string, changes: Record<string, unknown>) {
  return (raw: unknown): unknown => {
    const data = raw as Journalish;
    if (data.lesson?.id === lessonId) {
      const { comment, ...lesson } = changes;
      return {
        ...data,
        lesson: { ...data.lesson, ...lesson },
        ...(comment === undefined ? {} : { comment }),
      };
    }
    if (data.lessons?.some((l) => l.id === lessonId) && typeof changes.topic === "string") {
      return {
        ...data,
        lessons: data.lessons.map((l) => (l.id === lessonId ? { ...l, topic: changes.topic } : l)),
      };
    }
    return raw;
  };
}

export function isPendingId(id: string): boolean {
  return id.startsWith(PENDING);
}
