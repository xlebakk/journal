import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, isApiError, type Schemas } from "@/shared/api/client";

export type Me = Schemas["Me"];
export type Role = Schemas["RoleEnum"];
export type LoginStep = "done" | "totp";
export type Session = Schemas["Session"];

export const ME_KEY = ["me"] as const;

/** The current user, or null when not logged in. */
export function useMe() {
  return useQuery({
    queryKey: ME_KEY,
    queryFn: async () => {
      try {
        return await api<Me>("/me");
      } catch (error) {
        if (isApiError(error, 401)) return null;
        throw error;
      }
    },
    staleTime: 60_000,
  });
}

export function useBranding() {
  // Also sets the CSRF cookie needed for the login POST.
  return useQuery({
    queryKey: ["branding"],
    queryFn: () => api<Schemas["Branding"]>("/auth/login"),
    staleTime: Infinity,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { login: string; password: string; remember: boolean }) =>
      api<{ step: LoginStep }>("/auth/login", { method: "POST", body }),
    onSuccess: async (data) => {
      if (data.step === "done") await queryClient.invalidateQueries({ queryKey: ME_KEY });
    },
  });
}

export function useTotpLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      api<{ step: LoginStep }>("/auth/totp", { method: "POST", body: { code } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

/** Ends the server session and forgets everything cached on this device (SPEC §4). */
export async function logout(): Promise<void> {
  try {
    await api("/auth/logout", { method: "POST" });
  } finally {
    if ("caches" in window) {
      const names = await caches.keys().catch(() => []);
      await Promise.all(names.map((name) => caches.delete(name)));
    }
    window.location.assign("/login");
  }
}

export function useChangePassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { current_password: string; new_password: string }) =>
      api<void>("/auth/password", { method: "POST", body }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
}

export function useSwitchRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (role: Role) => api<Me>("/auth/role", { method: "POST", body: { role } }),
    onSuccess: (me) => {
      // Cached data belongs to the previous role.
      queryClient.clear();
      queryClient.setQueryData(ME_KEY, me);
    },
  });
}

export function reauthenticate(password: string): Promise<void> {
  return api<void>("/auth/reauth", { method: "POST", body: { password } });
}

export function useSessions() {
  return useQuery({ queryKey: ["sessions"], queryFn: () => api<Session[]>("/auth/sessions") });
}

export function useEndSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<void>(`/auth/sessions/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useEndOtherSessions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api<{ ended: number }>("/auth/sessions/end-others", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sessions"] }),
  });
}

export function useTotpSetup(enabled: boolean) {
  return useQuery({
    queryKey: ["totp-setup"],
    queryFn: () => api<Schemas["TotpSetup"]>("/auth/totp/setup"),
    enabled,
    staleTime: Infinity,
    gcTime: 0,
  });
}

export function useConfirmTotp() {
  return useMutation({
    mutationFn: (code: string) =>
      api<{ backup_codes: string[] }>("/auth/totp/setup", { method: "POST", body: { code } }),
  });
}

/** Where each role lands after login (SPEC §4). */
export function homePath(role: Role | null | undefined): string {
  switch (role) {
    case "admin":
      return "/admin";
    case "teacher":
      return "/teacher";
    case "student":
      return "/student";
    default:
      return "/login";
  }
}
