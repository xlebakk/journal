import { t } from "@/shared/i18n";

import styles from "./JournalGrid.module.css";

export type AttendanceMark = "present" | "late" | "absent" | "excused";

type JournalCellProps = {
  grades?: number[];
  attendance?: AttendanceMark;
  /** Grades strictly below this value are written in red pen. */
  lowBelow: number;
};

const SHORT: Record<Exclude<AttendanceMark, "present">, string> = {
  absent: t("attendance.absentShort"),
  late: t("attendance.lateShort"),
  excused: t("attendance.excusedShort"),
};

/** Contents of one grid cell. Colour is never the only signal: marks are letters. */
export function JournalCell({ grades = [], attendance = "present", lowBelow }: JournalCellProps) {
  return (
    <span className={styles.cell}>
      {attendance !== "present" && (
        <span className={styles[attendance]}>
          <span aria-hidden="true">{SHORT[attendance]}</span>
          <span className="visually-hidden">{t(`attendance.${attendance}`)}</span>
        </span>
      )}
      {grades.map((grade, index) => (
        <span key={index} className={grade < lowBelow ? styles.low : styles.grade}>
          {grade}
        </span>
      ))}
    </span>
  );
}
