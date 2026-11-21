import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type Group = Schemas["Group"];
export type Membership = Schemas["Membership"];
export type Course = Schemas["Course"];
export type Person = Schemas["Person"];
export type Year = Schemas["AcademicYear"];
export type Subject = Schemas["Subject"];

export function useGroups(archived = false) {
  return useQuery({
    queryKey: ["admin", "groups", { archived }],
    queryFn: () =>
      api<Group[]>("/admin/groups", { query: { archived: archived ? "true" : undefined } }),
  });
}

export function useGroup(id: string) {
  return useQuery({
    queryKey: ["admin", "groups", id],
    queryFn: () => api<Group>(`/admin/groups/${id}`),
  });
}

export function useMembers(id: string) {
  return useQuery({
    queryKey: ["admin", "groups", id, "members"],
    queryFn: () => api<Membership[]>(`/admin/groups/${id}/members`),
  });
}

export function useCourses(query: { group?: string; year?: string } = {}) {
  return useQuery({
    queryKey: ["admin", "courses", query],
    queryFn: () => api<Course[]>("/admin/courses", { query }),
  });
}

export function useYears() {
  return useQuery({
    queryKey: ["admin", "catalog", "/admin/years", {}],
    queryFn: () => api<Year[]>("/admin/years"),
  });
}

export function useSubjects() {
  return useQuery({
    queryKey: ["admin", "catalog", "/admin/subjects", {}],
    queryFn: () => api<Subject[]>("/admin/subjects"),
  });
}

export function useTeachers() {
  return useQuery({
    queryKey: ["admin", "teachers"],
    queryFn: () => api<Person[]>("/admin/teachers"),
    staleTime: 60_000,
  });
}

export function useInvalidateAdmin() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: ["admin"] });
}
