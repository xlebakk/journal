import { t } from "@/shared/i18n";
import { Dialog } from "@/shared/ui";
import type { ScheduleWarning } from "@/shared/ui/ScheduleIssues";

import { LessonWizard } from "./LessonWizard";

/** Where the lesson was asked for: a free place in the grid, or just «добавить занятие». */
export type AddAt = { date?: string; time?: string; group?: string };

/** A one-off lesson (consultation, mock test), built step by step (stage 19). */
export function ExtraLessonDialog({
  at,
  today,
  onClose,
}: {
  at: AddAt | null;
  today: string;
  onClose: (warnings: ScheduleWarning[]) => void;
}) {
  return (
    <Dialog
      open={at !== null}
      onOpenChange={(o) => !o && onClose([])}
      title={t("schedule.addLesson")}
    >
      {at && (
        <LessonWizard
          mode="lesson"
          today={today}
          presetDate={at.date}
          presetTime={at.time}
          presetGroup={at.group}
          onDone={onClose}
          onCancel={() => onClose([])}
        />
      )}
    </Dialog>
  );
}
