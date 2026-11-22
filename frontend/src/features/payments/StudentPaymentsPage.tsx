import { useState } from "react";
import { Link, useParams } from "react-router";

import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { centerToday } from "@/shared/lib/week";
import {
  Button,
  Dialog,
  DialogActions,
  EmptyState,
  RuledSkeleton,
  SelectField,
  TextField,
} from "@/shared/ui";

import { METHODS, money, useLedger, usePaymentsMutation, type AdminLedger } from "./api";
import { LedgerTable } from "./LedgerTable";
import local from "./Payments.module.css";

type Entry = AdminLedger["entries"][number];

function Totals({ ledger }: { ledger: AdminLedger }) {
  return (
    <dl className={styles.facts}>
      <dt>{t("payments.charged")}</dt>
      <dd className={`mono ${local.amount}`}>{money(ledger.charged)}</dd>
      <dt>{t("payments.paid")}</dt>
      <dd className={`mono ${local.amount}`}>{money(ledger.paid)}</dd>
      <dt>{t("payments.debt")}</dt>
      <dd className={`mono ${local.amount} ${ledger.debt > 0 ? local.debt : ""}`}>
        {ledger.debt < 0
          ? t("payments.advance", { amount: money(-ledger.debt) })
          : money(ledger.debt)}
      </dd>
    </dl>
  );
}

function DiscountForm({ ledger }: { ledger: AdminLedger }) {
  const [percent, setPercent] = useState(String(ledger.discount_percent));
  const save = usePaymentsMutation((value: number) =>
    api<void>(`/admin/payments/students/${ledger.student}/discount`, {
      method: "PUT",
      body: { percent: value },
    }),
  );
  const value = Number(percent || "0");
  return (
    <form
      className={styles.toolbar}
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(value);
      }}
    >
      <TextField
        label={t("payments.discountField")}
        className={local.amountField}
        type="number"
        min={0}
        max={100}
        value={percent}
        onChange={(e) => setPercent(e.target.value)}
        hint={t("payments.discountHint")}
        error={save.error ? errorMessage(save.error) : undefined}
      />
      <Button
        type="submit"
        disabled={save.isPending || value === ledger.discount_percent || value < 0 || value > 100}
      >
        {t("common.save")}
      </Button>
    </form>
  );
}

function PaymentForm({ ledger }: { ledger: AdminLedger }) {
  const empty = { amount: "", paid_on: centerToday(), method: "cash", comment: "" };
  const [form, setForm] = useState(empty);
  const pay = usePaymentsMutation(() =>
    api<AdminLedger>(`/admin/payments/students/${ledger.student}/payments`, {
      method: "POST",
      body: { ...form, amount: Number(form.amount) },
    }),
  );
  const set = (key: keyof typeof empty) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        pay.mutate(undefined, { onSuccess: () => setForm(empty) });
      }}
    >
      <div className={styles.toolbar}>
        <TextField
          label={t("payments.amount")}
          className={local.amountField}
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          required
          value={form.amount}
          onChange={set("amount")}
          error={fieldError(pay.error, "amount")}
        />
        <TextField
          label={t("payments.date")}
          type="date"
          required
          max={centerToday()}
          value={form.paid_on}
          onChange={set("paid_on")}
          error={fieldError(pay.error, "paid_on")}
        />
        <SelectField
          label={t("payments.methodField")}
          value={form.method}
          onChange={set("method")}
          options={METHODS.map((m) => ({ value: m, label: t(`payments.method.${m}`) }))}
        />
      </div>
      <TextField
        label={t("payments.comment")}
        value={form.comment}
        maxLength={300}
        onChange={set("comment")}
      />
      <div className={styles.toolbar}>
        <Button type="submit" variant="primary" disabled={pay.isPending || !form.amount}>
          {t("payments.accept")}
        </Button>
      </div>
      {pay.isSuccess && (
        <p className={styles.success} role="status">
          {t("payments.accepted")}
        </p>
      )}
      {pay.error && !fieldError(pay.error, "amount") && !fieldError(pay.error, "paid_on") && (
        <p className={styles.error} role="alert">
          {errorMessage(pay.error)}
        </p>
      )}
    </form>
  );
}

function VoidDialog({ entry, onClose }: { entry: Entry | null; onClose: () => void }) {
  const [reason, setReason] = useState("");
  const kind = entry?.kind === "charge" ? "charges" : "payments";
  const run = usePaymentsMutation(() =>
    api<void>(`/admin/payments/${kind}/${entry?.id}/void`, { method: "POST", body: { reason } }),
  );
  return (
    <Dialog
      open={entry !== null}
      onOpenChange={(open) => {
        if (!open) {
          setReason("");
          onClose();
        }
      }}
      title={t("payments.voidTitle")}
      description={entry ? `${money(entry.amount)} · ${t("payments.voidText")}` : undefined}
    >
      <TextField
        label={t("payments.voidReason")}
        value={reason}
        maxLength={300}
        onChange={(e) => setReason(e.target.value)}
      />
      {run.error && (
        <p className={styles.error} role="alert">
          {errorMessage(run.error)}
        </p>
      )}
      <DialogActions>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
        <Button
          variant="danger"
          disabled={!reason.trim() || run.isPending}
          onClick={() =>
            run.mutate(undefined, {
              onSuccess: () => {
                setReason("");
                onClose();
              },
            })
          }
        >
          {t("payments.void")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

/** One student's account for the administrator: totals, discount, a payment, the history. */
export function StudentPaymentsPage() {
  const { id = "" } = useParams();
  const ledger = useLedger(id);
  const [voiding, setVoiding] = useState<Entry | null>(null);
  if (ledger.isPending) return <RuledSkeleton rows={8} />;
  if (ledger.error || !ledger.data) {
    return <p className={styles.error}>{errorMessage(ledger.error)}</p>;
  }
  const data = ledger.data;
  return (
    <section className={styles.page}>
      <Link to="/admin/payments">{t("payments.back")}</Link>
      <h1>{data.full_name}</h1>
      <Totals ledger={data} />
      <section className={styles.section} aria-labelledby="pay-title">
        <h2 id="pay-title">{t("payments.acceptTitle")}</h2>
        <PaymentForm ledger={data} />
      </section>
      <section className={styles.section} aria-labelledby="discount-title">
        <h2 id="discount-title">{t("payments.discount")}</h2>
        <DiscountForm key={data.discount_percent} ledger={data} />
      </section>
      <section className={styles.section} aria-labelledby="history-title">
        <h2 id="history-title">{t("payments.history")}</h2>
        {data.entries.length === 0 ? (
          <EmptyState text={t("payments.noEntries")} />
        ) : (
          <LedgerTable entries={data.entries} onVoid={setVoiding} />
        )}
      </section>
      <VoidDialog entry={voiding} onClose={() => setVoiding(null)} />
    </section>
  );
}
