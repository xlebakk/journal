import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { weekRange, type Lesson, type Slot } from "@/features/schedule/api";
import { api, ApiError, type Schemas } from "@/shared/api/client";
import type { ScheduleConflict, ScheduleWarning } from "@/shared/ui/ScheduleIssues";

export type LessonType = Schemas["LessonType"];
export type Plan = {
  updated: string[];
  removed: string[];
  added: string[];
  kept_exceptions: string[];
};
export type Filters = { group?: string; teacher?: string; room?: string };

export function useAdminLessons(monday: string, filters: Filters) {
  return useQuery({
    queryKey: ["admin", "lessons", monday, filters],
    queryFn: () => api<Lesson[]>("/admin/lessons", { query: { ...weekRange(monday), ...filters } }),
    placeholderData: keepPreviousData,
  });
}

export function useSlots(filters: Filters) {
  return useQuery({
    queryKey: ["admin", "slots", filters],
    queryFn: () => api<Slot[]>("/admin/slots", { query: filters }),
  });
}

export function useLessonTypes() {
  return useQuery({
    queryKey: ["admin", "catalog", "/admin/lesson-types", {}],
    queryFn: () => api<LessonType[]>("/admin/lesson-types"),
    staleTime: 5 * 60_000,
  });
}

/** Conflicts and plan from a 409, warnings from a success. */
export function issuesOf(error: unknown): { conflicts: ScheduleConflict[]; plan: Plan | null } {
  if (!(error instanceof ApiError) || error.status !== 409) return { conflicts: [], plan: null };
  return {
    conflicts: error.field<ScheduleConflict[]>("conflicts") ?? [],
    plan: error.field<Plan>("plan") ?? null,
  };
}

export function warningsOf(data: unknown): ScheduleWarning[] {
  return ((data as { warnings?: ScheduleWarning[] } | undefined)?.warnings ??
    []) as ScheduleWarning[];
}
