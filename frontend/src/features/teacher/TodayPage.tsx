import { t } from "@/shared/i18n";
import { EmptyState } from "@/shared/ui";

export function TodayPage() {
  return (
    <section>
      <h1>{t("nav.today")}</h1>
      <EmptyState text={t("placeholder.teacherToday")} />
    </section>
  );
}
