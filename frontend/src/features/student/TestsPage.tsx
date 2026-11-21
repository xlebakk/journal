import { t } from "@/shared/i18n";
import { EmptyState } from "@/shared/ui";

/** «Тесты»: mock exams arrive in stage 5 (SPEC §6.4, §14). */
export function TestsPage() {
  return (
    <section>
      <h1>{t("student.tests")}</h1>
      <EmptyState text={t("student.testsSoon")} />
    </section>
  );
}
