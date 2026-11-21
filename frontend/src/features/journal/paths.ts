export function journalBase(role: string | null | undefined): string {
  return role === "admin" ? "/admin/journal" : "/teacher/journal";
}
