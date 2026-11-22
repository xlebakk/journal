import { Link } from "react-router";

import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { EmptyState, RuledSkeleton } from "@/shared/ui";

import { money, useMyPayments } from "./api";
import { LedgerTable } from "./LedgerTable";
import local from "./Payments.module.css";

/** «Оплата» for the student: what was charged, what was paid, what is left. */
export function MyPaymentsPage() {
  const ledger = useMyPayments();
  if (ledger.isPending) return <RuledSkeleton rows={6} />;
  if (ledger.error || !ledger.data) {
    return <p className={styles.error}>{errorMessage(ledger.error)}</p>;
  }
  const data = ledger.data;
  return (
    <section className={styles.page}>
      <h1>{t("payments.myTitle")}</h1>
      <p className={`${local.balance} ${data.debt > 0 ? local.debt : ""}`}>
        {data.debt > 0
          ? t("payments.myDebt", { amount: money(data.debt) })
          : data.debt < 0
            ? t("payments.myAdvance", { amount: money(-data.debt) })
            : t("payments.myClear")}
      </p>
      {data.discount_percent > 0 && (
        <p className={styles.note}>
          {t("payments.myDiscount", { percent: data.discount_percent })}
        </p>
      )}
      <p className={styles.note}>{t("payments.myHint")}</p>
      {data.entries.length === 0 ? (
        <EmptyState text={t("payments.noEntries")} />
      ) : (
        <LedgerTable entries={data.entries} />
      )}
    </section>
  );
}

/** A line on the student's home page while there is a debt. */
export function DebtNotice() {
  const ledger = useMyPayments();
  const debt = ledger.data?.debt ?? 0;
  if (debt <= 0) return null;
  return (
    <p className={`${local.notice} ${local.debt}`}>
      {t("payments.myDebt", { amount: money(debt) })}{" "}
      <Link to="/student/payments" className={local.noticeLink}>
        {t("payments.more")}
      </Link>
    </p>
  );
}
