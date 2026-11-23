import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, type Schemas } from "@/shared/api/client";

export type UserListItem = Schemas["AdminUserList"];
export type UserDetail = Schemas["AdminUserDetail"];
export type UserWrite = Schemas["AdminUserWriteRequest"];
export type AdminSection = NonNullable<UserWrite["admin_sections"]>[number];
export type UserStatus = "active" | "blocked" | "archived";

export type UserFilters = {
  q: string;
  role: string;
  status: string;
  page: number;
  subject?: string;
};

const USERS_KEY = ["admin", "users"] as const;

export function useUsers(filters: UserFilters) {
  return useQuery({
    queryKey: [...USERS_KEY, filters],
    queryFn: () =>
      api<Schemas["PaginatedAdminUserListList"]>("/admin/users", {
        query: {
          q: filters.q.trim() || undefined,
          role: filters.role || undefined,
          subject: filters.subject || undefined,
          status: filters.status || undefined,
          page: filters.page > 1 ? String(filters.page) : undefined,
        },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useUser(id: string) {
  return useQuery({
    queryKey: [...USERS_KEY, "detail", id],
    queryFn: () => api<UserDetail>(`/admin/users/${id}`),
  });
}

export function useUserSessions(id: string) {
  return useQuery({
    queryKey: [...USERS_KEY, "sessions", id],
    queryFn: () => api<Schemas["Session"][]>(`/admin/users/${id}/sessions`),
  });
}

export const usersApi = {
  create: (body: UserWrite) => api<UserDetail>("/admin/users", { method: "POST", body }),
  update: (id: string, body: Partial<UserWrite>) =>
    api<UserDetail>(`/admin/users/${id}`, { method: "PATCH", body }),
  action: (id: string, action: string) =>
    api<UserDetail>(`/admin/users/${id}/${action}`, { method: "POST" }),
  setPassword: (id: string, body: { password: string; must_change_password: boolean }) =>
    api<UserDetail>(`/admin/users/${id}/reset-password`, { method: "POST", body }),
  endSession: (id: string, sessionId: string) =>
    api<void>(`/admin/users/${id}/sessions/${sessionId}`, { method: "DELETE" }),
  endAllSessions: (id: string) =>
    api<{ ended: number }>(`/admin/users/${id}/sessions/end-all`, { method: "POST" }),
};

export function useInvalidateUsers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: USERS_KEY });
}
