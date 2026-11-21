import { t } from "@/shared/i18n";
import { EmptyState } from "@/shared/ui";

export function HomePage() {
  return (
    <section>
      <h1>{t("nav.home")}</h1>
      <EmptyState text={t("placeholder.studentHome")} />
    </section>
  );
}
