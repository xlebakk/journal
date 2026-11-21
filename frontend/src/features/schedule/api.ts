import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { api, type Schemas } from "@/shared/api/client";
import { addDays, centerToday, startOfWeek } from "@/shared/lib/week";

export type Lesson = Schemas["Lesson"];
export type StudentLesson = Schemas["StudentLesson"];
export type Slot = Schemas["Slot"];
export type ScheduleRequest = Schemas["ScheduleRequest"];
export type RoomOption = Schemas["RoomOption"];

/** The shown week lives in the URL (?week=YYYY-MM-DD, a Monday). */
export function useWeekParam(): [string, (monday: string) => void, string] {
  const [params, setParams] = useSearchParams();
  const today = centerToday();
  const raw = params.get("week");
  const monday = raw && /^\d{4}-\d{2}-\d{2}$/.test(raw) ? startOfWeek(raw) : startOfWeek(today);
  const setMonday = (value: string) => {
    const next = new URLSearchParams(params);
    if (value === startOfWeek(today)) next.delete("week");
    else next.set("week", value);
    setParams(next, { replace: true });
  };
  return [monday, setMonday, today];
}

export function weekRange(monday: string): { from: string; to: string } {
  return { from: monday, to: addDays(monday, 6) };
}

export function useStudentSchedule(monday: string) {
  return useQuery({
    queryKey: ["student", "schedule", monday],
    queryFn: () => api<StudentLesson[]>("/student/schedule", { query: weekRange(monday) }),
    placeholderData: keepPreviousData,
  });
}

export function useTeacherSchedule(monday: string) {
  return useQuery({
    queryKey: ["teacher", "schedule", monday],
    queryFn: () => api<Lesson[]>("/teacher/schedule", { query: weekRange(monday) }),
    placeholderData: keepPreviousData,
  });
}

export function useTeacherRequests() {
  return useQuery({
    queryKey: ["teacher", "schedule-requests"],
    queryFn: () => api<ScheduleRequest[]>("/teacher/schedule-requests"),
  });
}

export function useRooms() {
  return useQuery({
    queryKey: ["rooms"],
    queryFn: () => api<RoomOption[]>("/rooms"),
    staleTime: 5 * 60_000,
  });
}

export function useInvalidateSchedule() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["teacher"] }),
      queryClient.invalidateQueries({ queryKey: ["student"] }),
      queryClient.invalidateQueries({ queryKey: ["admin", "lessons"] }),
      queryClient.invalidateQueries({ queryKey: ["admin", "slots"] }),
      queryClient.invalidateQueries({ queryKey: ["admin", "schedule-requests"] }),
    ]);
}
