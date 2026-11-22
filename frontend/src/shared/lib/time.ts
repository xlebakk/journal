// "Today" is always computed in the center's time zone. Stage 1 reads it from settings.
import { language, names } from "@/shared/i18n";

export const CENTER_TIME_ZONE = "Asia/Tashkent";
// Digits come from Intl in Russian; Uzbek names of days and months — from the dictionary.
const LOCALE = "ru-RU";

function parts(date: Date, options: Intl.DateTimeFormatOptions): Record<string, string> {
  const result: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat(LOCALE, {
    timeZone: CENTER_TIME_ZONE,
    ...options,
  }).formatToParts(date)) {
    result[part.type] = part.value;
  }
  return result;
}

/** 21.11.2026 */
export function formatDate(date: Date): string {
  const p = parts(date, { day: "2-digit", month: "2-digit", year: "numeric" });
  return `${p.day}.${p.month}.${p.year}`;
}

/** Monday = 0 … Sunday = 6 for the date in the center's time zone. */
function weekdayIndex(date: Date): number {
  const p = parts(date, { day: "numeric", month: "numeric", year: "numeric" });
  return (
    (new Date(Date.UTC(Number(p.year), Number(p.month) - 1, Number(p.day))).getUTCDay() + 6) % 7
  );
}

/** 21.11.2026 · пятница — header line of the login page. */
export function formatJournalHeader(date: Date): string {
  const weekday =
    language() === "uz"
      ? names("dates.weekdays")[weekdayIndex(date)]
      : parts(date, { weekday: "long" }).weekday;
  return `${formatDate(date)} · ${weekday}`;
}

/** пт, 21 ноября */
export function formatHumanDate(date: Date): string {
  if (language() === "uz") {
    const p = parts(date, { day: "numeric", month: "numeric" });
    const month = names("dates.months")[Number(p.month) - 1];
    return `${names("dates.weekdaysShort")[weekdayIndex(date)]}, ${p.day}-${month}`;
  }
  const p = parts(date, { weekday: "short", day: "numeric", month: "long" });
  return `${p.weekday}, ${p.day} ${p.month}`;
}

/** пт, 21 ноября, 14:32 — from an ISO timestamp. */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return `${formatHumanDate(date)}, ${formatTime(date)}`;
}

/** 14:32 */
export function formatTime(date: Date): string {
  const p = parts(date, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${p.hour}:${p.minute}`;
}
