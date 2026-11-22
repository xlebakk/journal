import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { useMe } from "@/features/auth/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, upload } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, tMaybe } from "@/shared/i18n";
import { formatDate } from "@/shared/lib/week";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  FileField,
  Histogram,
  RuledSkeleton,
  Table,
  TextField,
} from "@/shared/ui";

import {
  examsBase,
  percentText,
  scoreText,
  useExamResults,
  useExamStats,
  useInvalidateExams,
  type Exam,
  type ExamImportResult,
  type ResultRow,
  type ResultsTable,
} from "./api";
import { ExamForm } from "./ExamForm";
import local from "./Exams.module.css";

type Tab = "results" | "import" | "stats";

/** One student's line: a total or one field per section, «не был», saved on change. */
function ResultLine({
  exam,
  row,
  editable,
  reason,
}: {
  exam: Exam;
  row: ResultRow;
  editable: boolean;
  reason: string;
}) {
  const queryClient = useQueryClient();
  const key = ["exams", exam.id, "results"];
  const [total, setTotal] = useState(row.total === null ? "" : String(row.total));
  const [parts, setParts] = useState<Record<string, string>>(() =>
    Object.fromEntries(exam.sections.map((s) => [s.id, String(row.sections[s.id] ?? "")])),
  );
  const replace = (next: ResultRow | null) =>
    queryClient.setQueryData<ResultsTable>(key, (old) =>
      old
        ? {
            ...old,
            rows: old.rows.map((r) =>
              r.student === row.student
                ? (next ?? {
                    ...r,
                    result: null,
                    total: null,
                    percent: null,
                    was_absent: false,
                    sections: {},
                    version: null,
                  })
                : r,
            ),
          }
        : old,
    );
  const save = useMutation({
    mutationFn: (absent: boolean) =>
      api<ResultRow>(`/exams/${exam.id}/results/${row.student}`, {
        method: "PUT",
        body: {
          was_absent: absent,
          total: exam.sections.length || absent || total === "" ? undefined : Number(total),
          sections:
            exam.sections.length && !absent
              ? Object.fromEntries(exam.sections.map((s) => [s.id, Number(parts[s.id])]))
              : undefined,
          version: row.version,
          reason,
        },
      }),
    onSuccess: (next) => {
      replace(next);
      setTotal(next.total === null ? "" : String(next.total));
    },
  });
  const clear = useMutation({
    mutationFn: () =>
      api(`/exams/${exam.id}/results/${row.student}/clear`, {
        method: "POST",
        body: { version: row.version, reason },
      }),
    onSuccess: () => {
      replace(null);
      setTotal("");
      setParts(Object.fromEntries(exam.sections.map((s) => [s.id, ""])));
    },
  });
  const complete = exam.sections.length
    ? exam.sections.every((s) => parts[s.id] !== "")
    : total !== "";
  const commit = () => {
    if (!complete) return;
    const changed = exam.sections.length
      ? exam.sections.some((s) => String(row.sections[s.id] ?? "") !== parts[s.id]) ||
        row.was_absent
      : String(row.total ?? "") !== total || row.was_absent;
    if (changed) save.mutate(false);
  };
  const error = save.error ?? clear.error;
  return (
    <tr>
      <th scope="row">
        {row.student_name}
        <span className={styles.status}> · {row.group_name}</span>
      </th>
      {exam.sections.map((s) => (
        <td key={s.id}>
          <input
            className={local.score}
            inputMode="numeric"
            aria-label={`${row.student_name}: ${s.name}`}
            value={row.was_absent ? "" : parts[s.id]}
            disabled={!editable || row.was_absent}
            onChange={(e) => setParts({ ...parts, [s.id]: e.target.value.replace(/\D/g, "") })}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && commit()}
          />
        </td>
      ))}
      <td className="mono">
        {exam.sections.length ? (
          scoreText(row.total, exam.max_score)
        ) : (
          <input
            className={local.score}
            inputMode="numeric"
            aria-label={`${row.student_name}: ${t("exams.total")}`}
            value={row.was_absent ? "" : total}
            disabled={!editable || row.was_absent}
            onChange={(e) => setTotal(e.target.value.replace(/\D/g, ""))}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && commit()}
          />
        )}
      </td>
      <td className="mono">{row.was_absent ? t("exams.absent") : percentText(row.percent)}</td>
      <td>
        <Checkbox
          label={t("exams.absent")}
          checked={row.was_absent}
          disabled={!editable || save.isPending}
          onChange={(e) => save.mutate(e.target.checked)}
        />
      </td>
      <td>
        {editable && row.result && (
          <Button onClick={() => clear.mutate()} disabled={clear.isPending}>
            {t("exams.clear")}
          </Button>
        )}
        {error && (
          <span className={styles.error} role="alert">
            {" "}
            {fieldError(error, "total") ?? fieldError(error, "sections") ?? errorMessage(error)}
          </span>
        )}
      </td>
    </tr>
  );
}

function ResultsTab({ data }: { data: ResultsTable }) {
  const [reason, setReason] = useState("");
  const { exam } = data;
  const closes = formatDate(data.window_closes_on);
  return (
    <div className={styles.section}>
      {data.locked === "future" && (
        <p className={styles.note}>{t("exams.lockedFuture", { date: formatDate(exam.date) })}</p>
      )}
      {data.locked === "window" && (
        <p className={styles.note}>{t("exams.lockedWindow", { date: closes })}</p>
      )}
      {data.needs_reason && (
        <>
          <p className={styles.note}>{t("exams.needsReason", { date: closes })}</p>
          <TextField
            label={t("exams.reason")}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </>
      )}
      {data.rows.length === 0 ? (
        <EmptyState text={t("exams.noStudents")} />
      ) : (
        <div className={local.scroller}>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("exams.student")}</th>
                {exam.sections.map((s) => (
                  <th key={s.id} scope="col">
                    {s.name} <span className={styles.status}>/ {s.max_score}</span>
                  </th>
                ))}
                <th scope="col">
                  {t("exams.total")} <span className={styles.status}>/ {exam.max_score}</span>
                </th>
                <th scope="col">{t("exams.percent")}</th>
                <th scope="col">{t("exams.absent")}</th>
                <th scope="col">
                  <span className="visually-hidden">{t("common.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <ResultLine
                  key={row.student}
                  exam={exam}
                  row={row}
                  editable={data.editable && (!data.needs_reason || reason.trim() !== "")}
                  reason={reason}
                />
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
}

function issueText(code: string): string {
  if (code.startsWith("bad_section:")) {
    return t("exams.badSection", { name: code.slice("bad_section:".length) });
  }
  return tMaybe(`errors.${code}`) ?? code;
}

function ImportTab({ data }: { data: ResultsTable }) {
  const invalidate = useInvalidateExams();
  const [file, setFile] = useState<File | null>(null);
  const [reason, setReason] = useState("");
  const send = useMutation({
    mutationFn: (apply: boolean) => {
      const form = new FormData();
      if (file) form.append("file", file);
      if (apply) form.append("apply", "true");
      if (reason) form.append("reason", reason);
      return upload<ExamImportResult>(`/exams/${data.exam.id}/import`, form);
    },
    onSuccess: async (result) => {
      if (result.applied) await invalidate();
    },
  });
  const result = send.data;
  const clean = result && result.rows.every((r) => r.issues.length === 0);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    send.mutate(false);
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <p className={styles.note}>{t("exams.importHint")}</p>
      <FileField
        label={t("exams.file")}
        accept=".xlsx,.csv"
        onChange={(e) => {
          setFile(e.target.files?.[0] ?? null);
          send.reset();
        }}
        error={fieldError(send.error, "file")}
      />
      {data.needs_reason && (
        <TextField
          label={t("exams.reason")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      )}
      <div className={styles.row}>
        <Button type="submit" disabled={!file || send.isPending || !data.editable}>
          {t("exams.preview")}
        </Button>
        {clean && !result.applied && (
          <Button variant="primary" onClick={() => send.mutate(true)} disabled={send.isPending}>
            {t("exams.apply")}
          </Button>
        )}
      </div>
      {send.error && !fieldError(send.error, "file") && (
        <p className={styles.error} role="alert">
          {errorMessage(send.error)}
        </p>
      )}
      {result?.applied && (
        <p className={styles.success} role="status">
          {t("exams.applied", { count: result.rows.length })}
        </p>
      )}
      {result && (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("exams.line")}</th>
              <th scope="col">{t("exams.student")}</th>
              <th scope="col">{t("exams.total")}</th>
              <th scope="col">{t("exams.issues")}</th>
            </tr>
          </thead>
          <tbody>
            {result.rows.map((r) => (
              <tr key={r.line}>
                <td className="mono">{r.line}</td>
                <td>{r.student_name || r.login || "—"}</td>
                <td className="mono">{r.was_absent ? t("exams.absent") : (r.total ?? "—")}</td>
                <td className={r.issues.length ? styles.error : styles.status}>
                  {r.issues.length ? r.issues.map(issueText).join("; ") : t("exams.ok")}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
    </form>
  );
}

function StatsTab({ id }: { id: string }) {
  const stats = useExamStats(id, true);
  if (stats.isPending) return <RuledSkeleton rows={4} />;
  if (stats.error || !stats.data)
    return <p className={styles.error}>{errorMessage(stats.error)}</p>;
  const { summary, exam } = stats.data;
  return (
    <div className={styles.section}>
      <dl className={styles.facts}>
        <dt>{t("exams.count")}</dt>
        <dd className="mono">{summary.count}</dd>
        <dt>{t("exams.absentCount")}</dt>
        <dd className="mono">{summary.absent}</dd>
        <dt>{t("exams.mean")}</dt>
        <dd className="mono">
          {summary.mean ?? "—"} · {percentText(stats.data.mean_percent)}
        </dd>
        <dt>{t("exams.median")}</dt>
        <dd className="mono">{summary.median ?? "—"}</dd>
        <dt>{t("exams.min")}</dt>
        <dd className="mono">{summary.min ?? "—"}</dd>
        <dt>{t("exams.max_")}</dt>
        <dd className="mono">
          {summary.max ?? "—"} / {exam.max_score}
        </dd>
      </dl>
      <h2>{t("exams.distribution")}</h2>
      <Histogram
        label={t("exams.distributionLabel")}
        buckets={stats.data.distribution.map((b) => ({
          key: String(b.from_percent),
          label: `${b.from_percent}–${b.to_percent}`,
          count: b.count,
        }))}
      />
      {stats.data.groups.length > 1 && (
        <>
          <h2>{t("exams.byGroup")}</h2>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("exams.group")}</th>
                <th scope="col">{t("exams.count")}</th>
                <th scope="col">{t("exams.mean")}</th>
                <th scope="col">{t("exams.meanPercent")}</th>
                <th scope="col">{t("exams.median")}</th>
              </tr>
            </thead>
            <tbody>
              {stats.data.groups.map((g) => (
                <tr key={g.group_name}>
                  <td>{g.group_name}</td>
                  <td className="mono">{g.count}</td>
                  <td className="mono">{g.mean ?? "—"}</td>
                  <td className="mono">{percentText(g.mean_percent)}</td>
                  <td className="mono">{g.median ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
      {stats.data.sections.length > 0 && (
        <>
          <h2>{t("exams.bySection")}</h2>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("exams.sectionName")}</th>
                <th scope="col">{t("exams.max")}</th>
                <th scope="col">{t("exams.mean")}</th>
                <th scope="col">{t("exams.meanPercent")}</th>
              </tr>
            </thead>
            <tbody>
              {stats.data.sections.map((s) => (
                <tr key={s.name}>
                  <td>{s.name}</td>
                  <td className="mono">{s.max_score}</td>
                  <td className="mono">{s.mean ?? "—"}</td>
                  <td className="mono">{percentText(s.mean_percent)}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </>
      )}
    </div>
  );
}

/** One test: results table, import from Excel, statistics. */
export function ExamPage() {
  const { id = "" } = useParams();
  const me = useMe();
  const base = examsBase(me.data?.active_role);
  const navigate = useNavigate();
  const invalidate = useInvalidateExams();
  const results = useExamResults(id);
  const [tab, setTab] = useState<Tab>("results");
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const remove = useMutation({
    mutationFn: () => api(`/exams/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      await invalidate();
      navigate(base);
    },
  });
  if (results.isPending) return <RuledSkeleton rows={8} />;
  if (results.error || !results.data) {
    return <p className={styles.error}>{errorMessage(results.error)}</p>;
  }
  const data = results.data;
  const { exam } = data;
  const tabs: [Tab, string][] = [
    ["results", t("exams.tabResults")],
    ["import", t("exams.tabImport")],
    ["stats", t("exams.tabStats")],
  ];
  return (
    <section className={styles.page}>
      <p>
        <Link to={base}>{t("exams.back")}</Link>
      </p>
      <div className={styles.titleRow}>
        <h1>{exam.title}</h1>
        <div className={styles.row}>
          <Button onClick={() => setEditing(true)}>{t("common.edit")}</Button>
          {exam.results_count === 0 && (
            <Button onClick={() => setDeleting(true)}>{t("exams.delete")}</Button>
          )}
        </div>
      </div>
      <p className={styles.note}>
        {exam.subject_name} · {formatDate(exam.date)} · {t("exams.max")} {exam.max_score} ·{" "}
        {exam.courses.map((c) => c.group_name).join(", ")}
      </p>
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
      {tab === "results" && <ResultsTab key={exam.version} data={data} />}
      {tab === "import" && <ImportTab data={data} />}
      {tab === "stats" && <StatsTab id={id} />}
      {editing && (
        <ExamForm
          open
          exam={exam}
          onClose={() => setEditing(false)}
          onSaved={() => setEditing(false)}
        />
      )}
      <Dialog
        open={deleting}
        onOpenChange={setDeleting}
        title={t("exams.delete")}
        description={t("exams.deleteConfirm", { title: exam.title })}
      >
        {remove.error && <p className={styles.error}>{errorMessage(remove.error)}</p>}
        <DialogActions>
          <Button variant="primary" onClick={() => remove.mutate()} disabled={remove.isPending}>
            {t("exams.delete")}
          </Button>
          <Button onClick={() => setDeleting(false)}>{t("common.cancel")}</Button>
        </DialogActions>
      </Dialog>
    </section>
  );
}
