import type { ScheduleRequest } from "@/features/schedule/api";
import { t } from "@/shared/i18n";
import { formatDayLong, hhmm } from "@/shared/lib/week";

export function requestSummary(request: ScheduleRequest): string {
  if (request.kind === "cancel") return t("schedule.kindCancel");
  const when = `${formatDayLong(request.proposed_date ?? "")} ${hhmm(request.proposed_start_time)}`;
  return t("schedule.kindMove", { when });
}
