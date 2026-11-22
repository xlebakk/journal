import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type Grid = Schemas["Grid"];
export type LessonPageData = Schemas["LessonPage"];
export type GridLesson = Schemas["GridLesson"];
export type Attendance = Schemas["Attendance"];
export type Grade = Schemas["Grade"];
export type RowStudent = Schemas["RowStudent"];
export type Rules = Schemas["JournalRules"];
export type WorkTypeOption = Schemas["WorkTypeOption"];
export type AttendanceStatus = Schemas["AttendanceStatusEnum"];
export type Today = Schemas["Today"];

export const STATUS_CYCLE: AttendanceStatus[] = ["present", "late", "absent", "excused"];
export const GRADABLE: AttendanceStatus[] = ["present", "late"];

export function useJournalCourses() {
  return useQuery({
    queryKey: ["journal", "courses"],
    queryFn: () => api<Schemas["CourseOption"][]>("/journal/courses"),
  });
}

export function useTerms(course: string | undefined) {
  return useQuery({
    queryKey: ["journal", "terms", course],
    queryFn: () => api<Schemas["TermOption"][]>(`/journal/courses/${course}/terms`),
    enabled: Boolean(course),
  });
}

export function useGrid(course: string | undefined, term: string | undefined) {
  return useQuery({
    queryKey: ["journal", "grid", course, term ?? "default"],
    queryFn: () =>
      api<Grid>(`/journal/courses/${course}`, {
        query: term === "year" ? { from: "1900-01-01", to: "2999-12-31" } : { term },
      }),
    enabled: Boolean(course),
    placeholderData: keepPreviousData,
  });
}

export function useLessonPage(id: string) {
  return useQuery({
    queryKey: ["journal", "lesson", id],
    queryFn: () => api<LessonPageData>(`/journal/lessons/${id}`),
  });
}

export function useTeacherToday() {
  return useQuery({ queryKey: ["journal", "today"], queryFn: () => api<Today>("/teacher/today") });
}

export function useInvalidateJournal() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["journal"] });
}

type Reason = { reason?: string };

/** Every write of the journal. `version` comes from the last response. */
export const journalApi = {
  lessonPage: (id: string) => api<LessonPageData>(`/journal/lessons/${id}`),
  updateLesson: (id: string, body: { version: number } & Reason & Record<string, unknown>) =>
    api<LessonPageData>(`/journal/lessons/${id}`, { method: "PATCH", body }),
  conduct: (id: string, body: { version: number } & Reason) =>
    api<LessonPageData>(`/journal/lessons/${id}/conduct`, { method: "POST", body }),
  setAttendance: (
    lesson: string,
    student: string,
    body: {
      status: AttendanceStatus;
      version?: number | null;
      late_minutes?: number | null;
      comment?: string;
    } & Reason,
  ) => api<Attendance>(`/journal/lessons/${lesson}/attendance/${student}`, { method: "PUT", body }),
  clearAttendance: (lesson: string, student: string, body: { version: number } & Reason) =>
    api<void>(`/journal/lessons/${lesson}/attendance/${student}/clear`, { method: "POST", body }),
  allPresent: (lesson: string, body: Reason) =>
    api<Attendance[]>(`/journal/lessons/${lesson}/attendance/all-present`, {
      method: "POST",
      body,
    }),
  addGrade: (
    lesson: string,
    body: {
      student: string;
      value: number;
      work_type?: string | null;
      comment?: string;
      client_key?: string;
    } & Reason,
  ) => api<Grade>(`/journal/lessons/${lesson}/grades`, { method: "POST", body }),
  updateGrade: (
    id: string,
    body: { version: number; value?: number; work_type?: string; comment?: string } & Reason,
  ) => api<Grade>(`/journal/grades/${id}`, { method: "PATCH", body }),
  deleteGrade: (id: string, body: { version: number } & Reason) =>
    api<Grade>(`/journal/grades/${id}/delete`, { method: "POST", body }),
  restoreGrade: (id: string, body: { version: number } & Reason) =>
    api<Grade>(`/journal/grades/${id}/restore`, { method: "POST", body }),
};

export const SCALE_RANGE: Record<string, [number, number]> = {
  "100": [0, 100],
  "5": [2, 5],
  "10": [1, 10],
};

export function isLow(value: number, rules: Rules): boolean {
  return value < Number(rules.low_below);
}
