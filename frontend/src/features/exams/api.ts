import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type Exam = Schemas["Exam"];
export type ResultsTable = Schemas["ResultsTable"];
export type ResultRow = Schemas["ResultRow"];
export type ExamStats = Schemas["ExamStats"];
export type DynamicsPoint = Schemas["DynamicsPoint"];
export type ExamImportRow = Schemas["ExamImportRow"];
export type ExamImportResult = Schemas["ImportResult"];
export type CourseOption = Schemas["CourseOption"];

export type ExamInput = {
  title: string;
  subject: string;
  date: string;
  max_score: number;
  courses: string[];
  sections: { name: string; max_score: number }[];
};

export function examsBase(role: string | null | undefined): string {
  return role === "admin" ? "/admin/exams" : "/teacher/exams";
}

export function useExams(subject?: string) {
  return useQuery({
    queryKey: ["exams", "list", subject ?? "all"],
    queryFn: () => api<Exam[]>("/exams", { query: { subject } }),
  });
}

export function useExamResults(id: string) {
  return useQuery({
    queryKey: ["exams", id, "results"],
    queryFn: () => api<ResultsTable>(`/exams/${id}/results`),
  });
}

export function useExamStats(id: string, enabled: boolean) {
  return useQuery({
    queryKey: ["exams", id, "stats"],
    queryFn: () => api<ExamStats>(`/exams/${id}/stats`),
    enabled,
  });
}

export function useDynamics(subject: string | undefined) {
  return useQuery({
    queryKey: ["exams", "dynamics", subject ?? "all"],
    queryFn: () => api<DynamicsPoint[]>("/exams/dynamics", { query: { subject } }),
    enabled: Boolean(subject),
  });
}

export function useExamCourses() {
  return useQuery({
    queryKey: ["journal", "courses"],
    queryFn: () => api<CourseOption[]>("/journal/courses"),
  });
}

export function useInvalidateExams() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["exams"] });
}

/** «24 / 30» */
export function scoreText(total: number | null, max: number): string {
  return total === null ? "—" : `${total} / ${max}`;
}

/** «62,3 %» from a server decimal string. */
export function percentText(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}
