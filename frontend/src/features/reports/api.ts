import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { useReauth } from "@/features/auth/reauthContext";
import { api, download, type Schemas } from "@/shared/api/client";

export type Statement = Schemas["CourseStatement"];
export type Performance = Schemas["Performance"];
export type FillRate = Schemas["FillRate"];
export type StudentSummary = Schemas["StudentSummary"];
export type Query = Record<string, string | undefined>;

export function useStatement(course: string | undefined, query: Query) {
  return useQuery({
    queryKey: ["reports", "course", course, query],
    queryFn: () => api<Statement>(`/reports/courses/${course}`, { query }),
    enabled: Boolean(course),
    placeholderData: keepPreviousData,
  });
}

export function usePerformance(query: Query) {
  return useQuery({
    queryKey: ["reports", "performance", query],
    queryFn: () => api<Performance>("/admin/reports/performance", { query }),
    placeholderData: keepPreviousData,
  });
}

export function useFillRate(query: Query) {
  return useQuery({
    queryKey: ["reports", "fill-rate", query],
    queryFn: () => api<FillRate>("/admin/reports/fill-rate", { query }),
    placeholderData: keepPreviousData,
  });
}

export function useStudentSummary(id: string, query: Query) {
  return useQuery({
    queryKey: ["reports", "student", id, query],
    queryFn: () => api<StudentSummary>(`/admin/reports/students/${id}`, { query }),
  });
}

/** XLSX/CSV export: personal data, so the password may be asked again (SPEC §8). */
export function useExport() {
  const withReauth = useReauth();
  return (path: string, query: Query, kind: "xlsx" | "csv") =>
    withReauth(() => download(path, { ...query, export: kind }));
}

/** «80,25» from a server decimal string; «—» for none. */
export function num(value: string | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return "—";
  return Number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}
