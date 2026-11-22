import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { t } from "@/shared/i18n";
import { useMediaQuery } from "@/shared/lib/useMediaQuery";
import {
  addDays,
  formatDayLong,
  formatDayMonth,
  formatDayShort,
  formatWeekRange,
  hhmm,
  isoWeekday,
  startOfWeek,
  weekDays,
  weekdayNames,
} from "@/shared/lib/week";

import { Button } from "./Button";
import { lessonMarks, type ScheduleItem } from "./scheduleMarks";
import styles from "./WeekSchedule.module.css";

type Options = { showGroup?: boolean; showTeacher?: boolean };

function Details({ item, showGroup, showTeacher }: { item: ScheduleItem } & Options) {
  return (
    <>
      <span className={`mono ${styles.time}`}>
        {hhmm(item.start_time)}–{hhmm(item.end_time)}
        {item.lesson_type_short && <span className={styles.type}> {item.lesson_type_short}</span>}
      </span>
      <span className={styles.subject}>{item.subject_name}</span>
      {showGroup && item.group_name && <span className={styles.meta}>{item.group_name}</span>}
      <span className={styles.meta}>
        {item.room_name ? t("schedule.room", { room: item.room_name }) : t("schedule.noRoom")}
        {showTeacher && !item.is_substituted && <> · {item.teacher_name}</>}
      </span>
      {lessonMarks(item).map((mark) => (
        <span key={mark.text} className={styles[mark.tone]}>
          {mark.text}
        </span>
      ))}
    </>
  );
}

type LessonProps = Options & {
  item: ScheduleItem;
  onSelect?: (item: ScheduleItem) => void;
};

function Lesson({ item, onSelect, ...options }: LessonProps) {
  const className = [styles.lesson, item.status === "cancelled" && styles.cancelled]
    .filter(Boolean)
    .join(" ");
  if (onSelect) {
    return (
      <button type="button" className={className} onClick={() => onSelect(item)}>
        <Details item={item} {...options} />
      </button>
    );
  }
  return (
    <div className={className}>
      <Details item={item} {...options} />
    </div>
  );
}

type WeekScheduleProps = Options & {
  monday: string;
  today: string;
  lessons: ScheduleItem[];
  onSelect?: (item: ScheduleItem) => void;
};

/**
 * Desktop: a ruled timetable — rows are start times, columns are days, like a paper
 * schedule. Lessons of different groups at the same time share a cell. Phone: a list by
 * day.
 */
export function WeekSchedule({ monday, today, lessons, onSelect, ...options }: WeekScheduleProps) {
  const phone = useMediaQuery("(max-width: 599px)");
  const days = useMemo(() => weekDays(monday), [monday]);
  const cells = useMemo(() => {
    const map = new Map<string, ScheduleItem[]>();
    for (const lesson of lessons) {
      const key = `${lesson.date} ${hhmm(lesson.start_time)}`;
      map.set(key, [...(map.get(key) ?? []), lesson]);
    }
    return map;
  }, [lessons]);
  const byDay = (day: string) => lessons.filter((lesson) => lesson.date === day);
  // Sunday only when something happens on it.
  const shown = days.filter((day, i) => i < 6 || byDay(day).length > 0);

  if (phone) {
    return (
      <div className={styles.list}>
        {shown.map((day) => {
          const items = byDay(day);
          const isToday = day === today;
          return (
            <section key={day} className={styles.listDay} aria-label={formatDayLong(day)}>
              <h3
                className={isToday ? `${styles.listHeading} ${styles.today}` : styles.listHeading}
              >
                {formatDayLong(day)}
                {isToday && <span className="visually-hidden"> ({t("schedule.today")})</span>}
              </h3>
              {items.length === 0 ? (
                <p className={styles.emptyDay}>{t("schedule.emptyDay")}</p>
              ) : (
                items.map((item) => (
                  <Lesson key={item.id} item={item} onSelect={onSelect} {...options} />
                ))
              )}
            </section>
          );
        })}
      </div>
    );
  }

  const times = [...new Set(lessons.map((lesson) => hhmm(lesson.start_time)))].sort();
  return (
    <div className={styles.scroller}>
      <table className={styles.timetable}>
        <caption className="visually-hidden">{formatWeekRange(monday)}</caption>
        <thead>
          <tr>
            <th scope="col" className={styles.timeHead}>
              <span className="visually-hidden">{t("schedule.start")}</span>
            </th>
            {shown.map((day) => (
              <th
                key={day}
                scope="col"
                className={day === today ? `${styles.dayHead} ${styles.today}` : styles.dayHead}
              >
                {formatDayShort(day)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {times.length === 0 ? (
            <tr>
              <td className={styles.timeCell} />
              <td colSpan={shown.length} className={styles.emptyWeek}>
                {t("schedule.empty")}
              </td>
            </tr>
          ) : (
            times.map((time) => (
              <tr key={time}>
                <th scope="row" className={`mono ${styles.timeCell}`}>
                  {time}
                </th>
                {shown.map((day) => (
                  <td
                    key={day}
                    className={day === today ? `${styles.cell} ${styles.todayCell}` : styles.cell}
                  >
                    {(cells.get(`${day} ${time}`) ?? []).map((item) => (
                      <Lesson key={item.id} item={item} onSelect={onSelect} {...options} />
                    ))}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The eDonish way for a teacher or a student: the week as a row of day cards, the chosen
 * day's lessons as a plain table underneath. One day at a time — less to read at once.
 */
export function DaySchedule({ monday, today, lessons, onSelect, ...options }: WeekScheduleProps) {
  const days = useMemo(() => weekDays(monday), [monday]);
  const byDay = (day: string) =>
    lessons
      .filter((lesson) => lesson.date === day)
      .sort((a, b) => a.start_time.localeCompare(b.start_time));
  const shown = days.filter((day, i) => i < 6 || byDay(day).length > 0);
  const initial = shown.includes(today)
    ? today
    : (shown.find((day) => byDay(day).length > 0) ?? shown[0] ?? monday);
  const [picked, setPicked] = useState<string | null>(null);
  const day = picked && shown.includes(picked) ? picked : initial;
  const items = byDay(day);
  const strip = useRef<HTMLDivElement>(null);
  // On a phone the strip scrolls: keep the chosen day in sight.
  useEffect(() => {
    strip.current
      ?.querySelector('[aria-selected="true"]')
      ?.scrollIntoView?.({ block: "nearest", inline: "center" });
  }, [day, monday]);
  return (
    <div className={styles.days}>
      <div
        ref={strip}
        className={styles.dayCards}
        role="tablist"
        aria-label={formatWeekRange(monday)}
      >
        {shown.map((d) => {
          const list = byDay(d);
          const last = list.at(-1);
          return (
            <button
              key={d}
              type="button"
              role="tab"
              aria-selected={d === day}
              className={d === today ? `${styles.dayCard} ${styles.dayCardToday}` : styles.dayCard}
              onClick={() => setPicked(d)}
            >
              <span className={styles.dayCardDate}>{formatDayMonth(d)}</span>
              <span className={styles.dayCardWeekday}>{weekdayNames()[isoWeekday(d) - 1]}</span>
              <span className={styles.dayCardMeta}>
                {list.length > 0
                  ? t("schedule.lessonsCount", { count: list.length })
                  : t("schedule.emptyDay")}
              </span>
              {last && <span className={styles.dayCardMeta}>{hhmm(last.end_time)}</span>}
            </button>
          );
        })}
      </div>
      <div role="tabpanel" className={styles.dayPanel} aria-label={formatDayLong(day)}>
        {items.length === 0 ? (
          <p className={styles.emptyDay}>{t("schedule.emptyDay")}</p>
        ) : (
          <table className={styles.dayTable}>
            <thead>
              <tr>
                <th scope="col">{t("schedule.start")}</th>
                <th scope="col">{t("schedule.end")}</th>
                <th scope="col">{t("schedule.subject")}</th>
                {options.showGroup && <th scope="col">{t("schedule.group")}</th>}
                <th scope="col">{t("schedule.roomFilter")}</th>
                {options.showTeacher && <th scope="col">{t("schedule.teacher")}</th>}
                <th scope="col">
                  <span className="visually-hidden">{t("schedule.status")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className={item.status === "cancelled" ? styles.dayRowCancelled : undefined}
                >
                  <td className="mono">{hhmm(item.start_time)}</td>
                  <td className="mono">{hhmm(item.end_time)}</td>
                  <td>
                    {onSelect ? (
                      <button
                        type="button"
                        className={styles.dayLink}
                        onClick={() => onSelect(item)}
                      >
                        {item.subject_name}
                      </button>
                    ) : (
                      item.subject_name
                    )}
                    {item.lesson_type_short && (
                      <span className={styles.type}> · {item.lesson_type_short}</span>
                    )}
                  </td>
                  {options.showGroup && <td>{item.group_name}</td>}
                  <td>{item.room_name ?? "—"}</td>
                  {options.showTeacher && <td>{item.teacher_name}</td>}
                  <td>
                    {lessonMarks(item).map((mark) => (
                      <span key={mark.text} className={styles[mark.tone]}>
                        {mark.text}{" "}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

type WeekNavProps = { monday: string; onChange: (monday: string) => void; onToday: () => void };

export function WeekNav({ monday, onChange, onToday }: WeekNavProps) {
  return (
    <div className={styles.nav}>
      <Button aria-label={t("schedule.previousWeek")} onClick={() => onChange(addDays(monday, -7))}>
        <ChevronLeft size={18} strokeWidth={1.5} aria-hidden="true" />
      </Button>
      <span className={styles.range}>{formatWeekRange(monday)}</span>
      <Button aria-label={t("schedule.nextWeek")} onClick={() => onChange(addDays(monday, 7))}>
        <ChevronRight size={18} strokeWidth={1.5} aria-hidden="true" />
      </Button>
      <Button onClick={onToday}>{t("schedule.today")}</Button>
    </div>
  );
}

/**
 * «Выбор периода» of the eDonish schedule: one wide pill with arrows at the ends and the week
 * in the middle; «сегодня» appears only away from the current week.
 */
export function PeriodBar({
  monday,
  today,
  onChange,
}: {
  monday: string;
  today: string;
  onChange: (monday: string) => void;
}) {
  const current = startOfWeek(today);
  return (
    <div className={styles.periodBar}>
      <button
        type="button"
        className={styles.periodArrow}
        aria-label={t("schedule.previousWeek")}
        onClick={() => onChange(addDays(monday, -7))}
      >
        <ChevronLeft size={20} strokeWidth={1.5} aria-hidden="true" />
      </button>
      <span className={styles.periodText}>
        <span aria-live="polite">{formatWeekRange(monday)}</span>
        {monday !== current && (
          <button type="button" className={styles.periodToday} onClick={() => onChange(current)}>
            {t("schedule.today")}
          </button>
        )}
      </span>
      <button
        type="button"
        className={styles.periodArrow}
        aria-label={t("schedule.nextWeek")}
        onClick={() => onChange(addDays(monday, 7))}
      >
        <ChevronRight size={20} strokeWidth={1.5} aria-hidden="true" />
      </button>
    </div>
  );
}
