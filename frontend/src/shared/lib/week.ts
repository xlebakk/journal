/**
 * Civil dates as ISO strings ("2026-11-16") — lessons are wall-clock events in the center's
 * time zone, so dates are never converted through the browser's zone.
 */
import { language, names } from "@/shared/i18n";

import { CENTER_TIME_ZONE } from "./time";

/** Today's date in the center's time zone. */
export function centerToday(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: CENTER_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
  return parts; // en-CA gives YYYY-MM-DD
}

function toUtc(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

function fromUtc(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(iso: string, days: number): string {
  const date = toUtc(iso);
  date.setUTCDate(date.getUTCDate() + days);
  return fromUtc(date);
}

/** ISO weekday: Monday = 1 … Sunday = 7. */
export function isoWeekday(iso: string): number {
  return ((toUtc(iso).getUTCDay() + 6) % 7) + 1;
}

/** Monday of the week containing the date (the week starts on Monday). */
export function startOfWeek(iso: string): string {
  return addDays(iso, 1 - isoWeekday(iso));
}

export function weekDays(monday: string): string[] {
  return Array.from({ length: 7 }, (_, i) => addDays(monday, i));
}

type DateParts = Pick<Intl.DateTimeFormatOptions, "weekday" | "day" | "month" | "year">;

/**
 * Russian through Intl. Tajik and English are assembled from the dictionary: most engines ship
 * no Tajik locale data, and one path keeps both alike: «дш, 16 ноябр 2026», «Mon, 16 November».
 */
function format(iso: string, options: DateParts): string {
  if (language() === "ru") {
    return new Intl.DateTimeFormat("ru-RU", { timeZone: "UTC", ...options }).format(toUtc(iso));
  }
  const [y, m, d] = iso.split("-").map(Number);
  const weekday = options.weekday
    ? names(options.weekday === "long" ? "dates.weekdays" : "dates.weekdaysShort")[
        isoWeekday(iso) - 1
      ]
    : "";
  const month = options.month ? names("dates.months")[(m ?? 1) - 1] : "";
  const day = options.day ? String(d) : "";
  const dayMonth = day && month ? `${day} ${month}` : day || month;
  const rest = [dayMonth, options.year ? String(y) : ""].filter(Boolean).join(" ");
  return weekday && rest ? `${weekday}, ${rest}` : weekday || rest;
}

/** «ноябрь 2026 г.» / «noyabr 2026» for "2026-11". */
export function formatMonth(month: string): string {
  return format(`${month}-01`, { month: "long", year: "numeric" });
}

/** «пн, 16 ноября» */
export function formatDayLong(iso: string): string {
  return format(iso, { weekday: "short", day: "numeric", month: "long" });
}

/** «16 ноября» / «16-noyabr» — a day card of the schedule. */
export function formatDayMonth(iso: string): string {
  return format(iso, { day: "numeric", month: "long" });
}

/** «пн 16.11» — compact column headers. */
export function formatDayShort(iso: string): string {
  const weekday = format(iso, { weekday: "short" });
  const [, m, d] = iso.split("-");
  return `${weekday} ${d}.${m}`;
}

/** «16.11.2026» */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

/** «16–22 ноября 2026» or «30 ноября – 6 декабря 2026». */
export function formatWeekRange(monday: string): string {
  const sunday = addDays(monday, 6);
  const sameMonth = monday.slice(0, 7) === sunday.slice(0, 7);
  const end = format(sunday, { day: "numeric", month: "long", year: "numeric" });
  const start = sameMonth
    ? format(monday, { day: "numeric" })
    : format(monday, { day: "numeric", month: "long" });
  return `${start}${sameMonth ? "–" : " – "}${end}`;
}

/** "14:00:00" → "14:00" */
export function hhmm(time: string | null | undefined): string {
  return time ? time.slice(0, 5) : "";
}

export function minutes(time: string): number {
  const [h, m] = time.split(":").map(Number);
  return (h ?? 0) * 60 + (m ?? 0);
}

/** «понедельник» … «воскресенье» (or «dushanba» … «yakshanba»), Monday first. */
export function weekdayNames(): string[] {
  return weekDays("2026-11-16").map((day) => format(day, { weekday: "long" }));
}

/** «ноябрь» / «noyabr»: the month over the columns of the journal. */
export function monthName(iso: string): string {
  return names("dates.months")[Number(iso.slice(5, 7)) - 1] ?? "";
}

/** «пн» … «вс» / «du» … «ya»: the weekday under a date in the journal. */
export function weekdayShort(iso: string): string {
  return names("dates.weekdaysShort")[isoWeekday(iso) - 1] ?? "";
}
