import { t } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";

export type ScheduleItem = {
  id: string;
  date: string;
  start_time: string;
  end_time: string;
  subject_name: string;
  subject_short: string;
  group_name?: string;
  teacher_name: string;
  room_name: string | null;
  lesson_type_short?: string | null;
  status: "planned" | "conducted" | "cancelled";
  cancel_reason: string;
  is_extra: boolean;
  is_moved: boolean;
  is_room_changed: boolean;
  is_substituted: boolean;
  planned_date: string;
  planned_start_time: string;
  planned_room_name: string | null;
};

type Tone = "red" | "pencil" | "ink";

/** Text marks: colour is never the only signal (SPEC §12). */
export function lessonMarks(item: ScheduleItem): { text: string; tone: Tone }[] {
  const marks: { text: string; tone: Tone }[] = [];
  if (item.status === "cancelled") marks.push({ text: t("schedule.cancelled"), tone: "red" });
  if (item.is_moved) {
    const when = `${formatDayLong(item.planned_date)} ${hhmm(item.planned_start_time)}`;
    marks.push({ text: t("schedule.movedFrom", { when }), tone: "pencil" });
  }
  if (item.is_substituted) {
    marks.push({ text: t("schedule.substitute", { name: item.teacher_name }), tone: "pencil" });
  }
  if (item.is_room_changed && item.planned_room_name) {
    const text = t("schedule.roomChanged", { room: item.planned_room_name });
    marks.push({ text, tone: "pencil" });
  }
  if (item.is_extra) marks.push({ text: t("schedule.extra"), tone: "ink" });
  return marks;
}
