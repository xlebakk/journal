import { useStudentSchedule, useWeekParam } from "@/features/schedule/api";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { DaySchedule, PeriodBar, RuledSkeleton } from "@/shared/ui";

import styles from "@/features/schedule/SchedulePage.module.css";

/** «Расписание» of a student: own groups only; changes are marked. */
export function SchedulePage() {
  const [monday, setMonday, today] = useWeekParam();
  const schedule = useStudentSchedule(monday);
  return (
    <section className={styles.page}>
      <h1 className="visually-hidden">{t("schedule.title")}</h1>
      <PeriodBar monday={monday} today={today} onChange={setMonday} />
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
