import { t } from "@/shared/i18n";
import { formatDate, formatMonth } from "@/shared/lib/week";
import { Table } from "@/shared/ui";

import { money, type AdminLedger, type Ledger } from "./api";
import local from "./Payments.module.css";

type Entry = Ledger["entries"][number] & Partial<AdminLedger["entries"][number]>;

function what(entry: Entry): string {
  if (entry.kind === "charge") {
    return t("payments.chargeFor", {
      month: formatMonth(entry.date.slice(0, 7)),
      group: entry.group_name,
    });
  }
  return t("payments.paymentBy", { method: t(`payments.method.${entry.method}` as never) });
}

function details(entry: Entry): string {
  if (entry.kind === "charge" && entry.discount_percent) {
    return t("payments.withDiscount", {
      full: money(entry.full_amount ?? 0),
      percent: entry.discount_percent,
    });
  }
  return entry.comment;
}

/** Charges and payments, newest first. The admin version shows authors and voids. */
export function LedgerTable<E extends Entry>({
  entries,
  onVoid,
}: {
  entries: E[];
  onVoid?: (entry: E) => void;
}) {
  return (
    <Table>
      <thead>
        <tr>
          <th scope="col">{t("payments.date")}</th>
          <th scope="col">{t("payments.operation")}</th>
          <th scope="col">{t("payments.amount")}</th>
          <th scope="col">{t("payments.details")}</th>
          {onVoid && <th scope="col">{t("payments.author")}</th>}
          {onVoid && (
            <th scope="col">
              <span className="visually-hidden">{t("common.actions")}</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id} className={entry.voided ? local.voided : undefined}>
            <td className="mono">{formatDate(entry.date)}</td>
            <td>{what(entry)}</td>
            <td className={`mono ${local.amount}`}>
              {entry.kind === "payment" ? "−" : "+"}
              {money(entry.amount)}
            </td>
            <td>
              {details(entry) || "—"}
              {entry.voided && (
                <span className={local.voidNote}>
                  {" "}
                  · {t("payments.voidedBecause", { reason: entry.void_reason ?? "" })}
                </span>
              )}
            </td>
            {onVoid && <td>{entry.author_name || t("audit.system")}</td>}
            {onVoid && (
              <td>
                {!entry.voided && (
                  <button type="button" className={local.linkButton} onClick={() => onVoid(entry)}>
                    {t("payments.void")}
                  </button>
                )}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
