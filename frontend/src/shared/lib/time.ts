// "Today" is always computed in the center's time zone (SPEC §2). Stage 1 reads it from settings.
export const CENTER_TIME_ZONE = "Asia/Tashkent";
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

/** 21.11.2026 · пятница — header line of the login page. */
export function formatJournalHeader(date: Date): string {
  return `${formatDate(date)} · ${parts(date, { weekday: "long" }).weekday}`;
}

/** пт, 21 ноября */
export function formatHumanDate(date: Date): string {
  const p = parts(date, { weekday: "short", day: "numeric", month: "long" });
  return `${p.weekday}, ${p.day} ${p.month}`;
}

/** 14:32 */
export function formatTime(date: Date): string {
  const p = parts(date, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  return `${p.hour}:${p.minute}`;
}
