import { Link } from "react-router";

import { t } from "@/shared/i18n";
import { EmptyState } from "@/shared/ui";

export function OverviewPage() {
  return (
    <section>
      <h1>{t("nav.overview")}</h1>
      <EmptyState
        text={t("placeholder.adminOverview")}
        action={<Link to="/admin/users">{t("nav.users")}</Link>}
      />
    </section>
  );
}
