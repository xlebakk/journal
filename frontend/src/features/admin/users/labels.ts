import { t, type MessageKey } from "@/shared/i18n";

export function statusLabel(status: string): string {
  const key = `users.status${status.charAt(0).toUpperCase()}${status.slice(1)}` as MessageKey;
  return t(key);
}
