import { useEffect, useState } from "react";
import { Link } from "react-router";

import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday, formatMonth } from "@/shared/lib/week";
import {
  Button,
  Checkbox,
  EmptyState,
  RuledSkeleton,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import {
  money,
  useGroupFees,
  usePaymentsMutation,
  usePaymentStudents,
  type GroupFees,
} from "./api";
import local from "./Payments.module.css";

type Tab = "students" | "groups";

function Billing({ fees }: { fees: GroupFees }) {
  const [month, setMonth] = useState(centerToday().slice(0, 7));
  const bill = usePaymentsMutation((value: string) =>
    api<{ created: number; existing: number }>("/admin/payments/bill", {
      method: "POST",
      body: { month: `${value}-01` },
    }),
  );
  return (
    <section className={styles.section} aria-labelledby="billing-title">
      <h2 id="billing-title">{t("payments.billing")}</h2>
      <p className={styles.note}>
        {t("payments.billingStatus", {
          month: formatMonth(fees.month.slice(0, 7)),
          count: fees.month_charges,
        })}
      </p>
      <div className={styles.toolbar}>
        <TextField
          label={t("payments.month")}
          type="month"
          value={month}
          max={centerToday().slice(0, 7)}
          onChange={(e) => setMonth(e.target.value)}
        />
        <Button variant="primary" onClick={() => bill.mutate(month)} disabled={bill.isPending}>
          {t("payments.bill", { month: month ? formatMonth(month) : "" })}
        </Button>
      </div>
      <p className={styles.note}>{t("payments.billingHint")}</p>
      {bill.data && (
        <p className={styles.success} role="status">
          {t("payments.billed", { created: bill.data.created, existing: bill.data.existing })}
        </p>
      )}
      {bill.error && (
        <p className={styles.error} role="alert">
          {errorMessage(bill.error)}
        </p>
      )}
    </section>
  );
}

function FeeRow({ group }: { group: GroupFees["groups"][number] }) {
  const [value, setValue] = useState(String(group.monthly_amount || ""));
  const save = usePaymentsMutation((amount: number) =>
    api<void>(`/admin/payments/groups/${group.id}`, {
      method: "PUT",
      body: { monthly_amount: amount },
    }),
  );
  const amount = Number(value || "0");
  const changed = amount !== group.monthly_amount;
  return (
    <tr>
      <td>
        {group.name}
        {group.is_archived && <span className={styles.status}> · {t("groups.archived")}</span>}
      </td>
      <td>{group.year_name}</td>
      <td className="mono">{group.members_count}</td>
      <td>
        <TextField
          label={t("payments.feeFor", { group: group.name })}
          className={local.amountField}
          type="number"
          inputMode="numeric"
          min={0}
          step={1000}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          error={save.error ? errorMessage(save.error) : undefined}
        />
      </td>
      <td>
        <Button
          onClick={() => save.mutate(amount)}
          disabled={!changed || save.isPending || !Number.isInteger(amount) || amount < 0}
        >
          {t("common.save")}
        </Button>
      </td>
    </tr>
  );
}

function GroupsTab() {
  const fees = useGroupFees();
  if (fees.isPending) return <RuledSkeleton rows={6} />;
  if (fees.error || !fees.data) return <p className={styles.error}>{errorMessage(fees.error)}</p>;
  return (
    <>
      <Billing fees={fees.data} />
      <section className={styles.section} aria-labelledby="fees-title">
        <h2 id="fees-title">{t("payments.fees")}</h2>
        <p className={styles.note}>{t("payments.feesHint")}</p>
        {fees.data.groups.length === 0 ? (
          <EmptyState text={t("groups.empty")} />
        ) : (
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("groups.name")}</th>
                <th scope="col">{t("groups.year")}</th>
                <th scope="col">{t("groups.members")}</th>
                <th scope="col">{t("payments.fee")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("common.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {fees.data.groups.map((group) => (
                <FeeRow key={`${group.id}-${group.monthly_amount}`} group={group} />
              ))}
            </tbody>
          </Table>
        )}
      </section>
    </>
  );
}

function StudentsTab() {
  const fees = useGroupFees();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [group, setGroup] = useState("");
  const [debtors, setDebtors] = useState(true);
  useEffect(() => {
    const timer = setTimeout(() => setSearch(q), 300);
    return () => clearTimeout(timer);
  }, [q]);
  const students = usePaymentStudents({ q: search, group, debtors });
  const data = students.data;
  return (
    <>
      <div className={styles.toolbar}>
        <TextField
          label={t("users.search")}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <SelectField
          label={t("payments.group")}
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          options={[
            { value: "", label: t("reports.anyGroup") },
            ...(fees.data?.groups ?? []).map((g) => ({ value: g.id, label: g.name })),
          ]}
        />
        <Checkbox
          label={t("payments.onlyDebtors")}
          checked={debtors}
          onChange={(e) => setDebtors(e.target.checked)}
        />
      </div>
      {data && (
        <p className={styles.note}>
          {t("payments.debtSummary", { count: data.debtors, total: money(data.debt_total) })}
        </p>
      )}
      {students.isPending ? (
        <RuledSkeleton rows={8} />
      ) : students.error || !data ? (
        <p className={styles.error}>{errorMessage(students.error)}</p>
      ) : data.rows.length === 0 ? (
        <EmptyState text={t(debtors ? "payments.noDebtors" : "payments.noStudents")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("payments.student")}</th>
              <th scope="col">{t("payments.groups")}</th>
              <th scope="col">{t("payments.discount")}</th>
              <th scope="col">{t("payments.charged")}</th>
              <th scope="col">{t("payments.paid")}</th>
              <th scope="col">{t("payments.debt")}</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.id}>
                <td>
                  <Link to={`/admin/payments/${row.id}`}>{row.full_name}</Link>
                </td>
                <td>{row.groups.join(", ") || "—"}</td>
                <td className="mono">{row.discount_percent ? `${row.discount_percent}%` : "—"}</td>
                <td className={`mono ${local.amount}`}>{money(row.charged)}</td>
                <td className={`mono ${local.amount}`}>{money(row.paid)}</td>
                <td className={`mono ${local.amount} ${row.debt > 0 ? local.debt : ""}`}>
                  {money(row.debt)}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </>
  );
}

/** «Оплаты»: debts, payments and monthly prices of groups. */
export function PaymentsPage() {
  const [tab, setTab] = useState<Tab>("students");
  const tabs: [Tab, string][] = [
    ["students", t("payments.tabStudents")],
    ["groups", t("payments.tabGroups")],
  ];
  return (
    <section className={styles.page}>
      <h1>{t("payments.title")}</h1>
      <div className={styles.tabs} role="tablist">
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            className={styles.tab}
            aria-selected={tab === value}
            onClick={() => setTab(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "students" ? <StudentsTab /> : <GroupsTab />}
    </section>
  );
}
