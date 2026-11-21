import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { useSubjects } from "@/features/admin/groups/api";
import page from "@/features/schedule/SchedulePage.module.css";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, SelectField, TextField } from "@/shared/ui";

type Target = Schemas["Target"];
type Row = { subject: string; percent: string };

function Editor({ userId, initial }: { userId: string; initial: Target[] }) {
  const subjects = useSubjects();
  const queryClient = useQueryClient();
  const [rows, setRows] = useState<Row[]>(
    initial.map((r) => ({ subject: r.subject, percent: String(r.percent) })),
  );
  const save = useMutation({
    mutationFn: () =>
      api<Target[]>(`/admin/users/${userId}/targets`, {
        method: "PUT",
        body: rows
          .filter((r) => r.subject && r.percent)
          .map((r) => ({ subject: r.subject, percent: Number(r.percent) })),
      }),
    onSuccess: (next) => queryClient.setQueryData(["admin", "targets", userId], next),
  });
  const options = (subjects.data ?? []).map((s) => ({ value: s.id, label: s.name }));
  const used = new Set(rows.map((r) => r.subject));
  const free = options.find((o) => !used.has(o.value));
  const set = (i: number, change: Partial<Row>) =>
    setRows(rows.map((r, j) => (j === i ? { ...r, ...change } : r)));
  return (
    <div className={page.form}>
      {rows.map((row, i) => (
        <div key={i} className={page.row}>
          <SelectField
            label={t("targets.subject")}
            value={row.subject}
            onChange={(e) => set(i, { subject: e.target.value })}
            options={options.filter((o) => o.value === row.subject || !used.has(o.value))}
          />
          <TextField
            label={t("targets.percent")}
            type="number"
            min={1}
            max={100}
            inputMode="numeric"
            value={row.percent}
            onChange={(e) => set(i, { percent: e.target.value })}
          />
          <Button onClick={() => setRows(rows.filter((_, j) => j !== i))}>
            {t("targets.remove")}
          </Button>
        </div>
      ))}
      <div className={page.row}>
        {free && (
          <Button onClick={() => setRows([...rows, { subject: free.value, percent: "80" }])}>
            {t("targets.add")}
          </Button>
        )}
        <Button variant="primary" onClick={() => save.mutate()} disabled={save.isPending}>
          {t("targets.save")}
        </Button>
      </div>
      {save.error && (
        <p className={page.error} role="alert">
          {errorMessage(save.error)}
        </p>
      )}
      {save.isSuccess && (
        <p className={page.success} role="status">
          {t("targets.saved")}
        </p>
      )}
    </div>
  );
}

/** A student's goals per subject in % (decision of stage 5) and the summary for parents. */
export function StudentExtras({ userId }: { userId: string }) {
  const targets = useQuery({
    queryKey: ["admin", "targets", userId],
    queryFn: () => api<Target[]>(`/admin/users/${userId}/targets`),
  });
  return (
    <section className={page.section} aria-labelledby="user-targets">
      <div className={page.titleRow}>
        <h2 id="user-targets">{t("targets.title")}</h2>
        <Link to={`/admin/reports/students/${userId}`}>{t("reports.summarySheet")}</Link>
      </div>
      <p className={page.note}>{t("targets.hint")}</p>
      {targets.data && <Editor userId={userId} initial={targets.data} />}
      {targets.error && <p className={page.error}>{errorMessage(targets.error)}</p>}
    </section>
  );
}
