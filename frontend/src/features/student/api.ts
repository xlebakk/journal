import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type StudentHome = Schemas["StudentHome"];
export type Diary = Schemas["Diary"];
export type DiaryLesson = Schemas["DiaryLesson"];
export type StudentGrades = Schemas["StudentGrades"];
export type StudentGrade = Schemas["StudentGrade"];
export type StudentAttendance = Schemas["StudentAttendance"];
export type StudentProfile = Schemas["StudentProfileView"];

export function useStudentHome() {
  return useQuery({
    queryKey: ["student", "home"],
    queryFn: () => api<StudentHome>("/student/home"),
  });
}

export function useDiary(monday: string) {
  return useQuery({
    queryKey: ["student", "diary", monday],
    queryFn: () => api<Diary>("/student/diary", { query: { week: monday } }),
    placeholderData: keepPreviousData,
  });
}

export function useStudentGrades(term: string | undefined) {
  return useQuery({
    queryKey: ["student", "grades", term ?? "default"],
    queryFn: () => api<StudentGrades>("/student/grades", { query: { term } }),
    placeholderData: keepPreviousData,
  });
}

export function useStudentAttendance(month: string | undefined) {
  return useQuery({
    queryKey: ["student", "attendance", month ?? "current"],
    queryFn: () => api<StudentAttendance>("/student/attendance", { query: { month } }),
    placeholderData: keepPreviousData,
  });
}

export function useStudentProfile(enabled: boolean) {
  return useQuery({
    queryKey: ["student", "profile"],
    queryFn: () => api<StudentProfile>("/student/profile"),
    enabled,
  });
}
