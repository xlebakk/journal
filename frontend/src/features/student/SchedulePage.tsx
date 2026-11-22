import { useStudentSchedule, useWeekParam } from "@/features/schedule/api";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { startOfWeek } from "@/shared/lib/week";
import { RuledSkeleton, WeekNav, DaySchedule } from "@/shared/ui";

import styles from "@/features/schedule/SchedulePage.module.css";

/** «Расписание» of a student: own groups only; changes are marked (SPEC §6.6). */
export function SchedulePage() {
  const [monday, setMonday, today] = useWeekParam();
  const schedule = useStudentSchedule(monday);
  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("schedule.title")}</h1>
        <WeekNav
          monday={monday}
          onChange={setMonday}
          onToday={() => setMonday(startOfWeek(today))}
        />
      </div>
      {schedule.isPending ? (
        <RuledSkeleton rows={6} />
      ) : schedule.error ? (
        <p className={styles.error}>{errorMessage(schedule.error)}</p>
      ) : (
        <DaySchedule monday={monday} today={today} lessons={schedule.data} showTeacher />
      )}
    </section>
  );
}
