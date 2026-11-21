import { useState } from "react";

import { useGroups, useSubjects } from "@/features/admin/groups/api";
import styles from "@/features/schedule/SchedulePage.module.css";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDate } from "@/shared/lib/week";
import { EmptyState, RuledSkeleton, SelectField, Table, TextField } from "@/shared/ui";

import { num, useFillRate, usePerformance, type Query } from "./api";
import { ExportButtons } from "./ExportButtons";
import { StatementPanel } from "./StatementPanel";

type Tab = "performance" | "fill" | "statement";

function PeriodFields({
  from,
  to,
  onChange,
}: {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
}) {
  return (
    <>
      <TextField
        label={t("reports.from")}
        type="date"
        value={from}
        onChange={(e) => onChange(e.target.value, to)}
      />
      <TextField
        label={t("reports.to")}
        type="date"
        value={to}
        onChange={(e) => onChange(from, e.target.value)}
      />
    </>
  );
}

function PerformanceTab() {
  const groups = useGroups();
  const subjects = useSubjects();
  const [group, setGroup] = useState("");
  const [subject, setSubject] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const query: Query = {
    group: group || undefined,
    subject: subject || undefined,
    from: from || undefined,
    to: to || undefined,
  };
  const report = usePerformance(query);
  const data = report.data;
  return (
    <div className={styles.section}>
      <div className={`${styles.toolbar} ${styles.noPrint}`}>
        <SelectField
          label={t("reports.group")}
          value={group}
          onChange={(e) => setGroup(e.target.value)}
          options={[
            { value: "", label: t("reports.anyGroup") },
            ...(groups.data ?? []).map((g) => ({ value: g.id, label: g.name })),
          ]}
        />
        <SelectField
          label={t("reports.subject")}
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          options={[
            { value: "", label: t("reports.anySubject") },
            ...(subjects.data ?? []).map((s) => ({ value: s.id, label: s.name })),
          ]}
        />
        <PeriodFields
          from={from}
          to={to}
          onChange={(f, tt) => {
            setFrom(f);
            setTo(tt);
          }}
        />
      </div>
      {report.isPending ? (
        <RuledSkeleton rows={5} />
      ) : report.error || !data ? (
        <p className={styles.error}>{errorMessage(report.error)}</p>
      ) : (
        <>
          <div className={styles.titleRow}>
            <p className={styles.note}>
              {t("reports.periodLine", { from: formatDate(data.first), to: formatDate(data.last) })}
            </p>
            <ExportButtons path="/admin/reports/performance" query={query} />
          </div>
          {data.courses.length === 0 ? (
            <EmptyState text={t("reports.empty")} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th scope="col">{t("reports.group")}</th>
                  <th scope="col">{t("reports.subject")}</th>
                  <th scope="col">{t("reports.teacher")}</th>
                  <th scope="col">{t("reports.students")}</th>
                  <th scope="col">{t("reports.average")}</th>
                  <th scope="col">{t("reports.attendance")}</th>
                  <th scope="col">{t("reports.lowAttendance")}</th>
                  <th scope="col">{t("reports.lowAverage")}</th>
                </tr>
              </thead>
              <tbody>
                {data.courses.map((row) => (
                  <tr key={row.course}>
                    <td>{row.group_name}</td>
                    <td>{row.subject_name}</td>
                    <td>{row.teacher_name}</td>
                    <td className="mono">{row.students}</td>
                    <td className="mono">{num(row.average)}</td>
                    <td className="mono">{num(row.attendance_percent, 0)}</td>
                    <td className={`mono ${row.low_attendance ? styles.error : ""}`}>
                      {row.low_attendance}
                    </td>
                    <td className={`mono ${row.low_average ? styles.error : ""}`}>
                      {row.low_average}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
          {data.students.length > 0 && (
            <>
              <h2>{t("reports.byStudents")}</h2>
              <Table>
                <thead>
                  <tr>
                    <th scope="col">{t("reports.student")}</th>
                    {data.courses.map((c) => (
                      <th key={c.course} scope="col">
                        {c.subject_name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.students.map((st) => (
                    <tr key={st.student}>
                      <th scope="row">{st.full_name}</th>
                      {st.cells.map((cell) => (
                        <td key={cell.course} className="mono">
                          {num(cell.average)}
                          <span className={styles.status}>
                            {" "}
                            · {num(cell.attendance_percent, 0)}%
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </Table>
            </>
          )}
        </>
      )}
    </div>
  );
}

function FillRateTab() {
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const query: Query = { from: from || undefined, to: to || undefined };
  const report = useFillRate(query);
  const data = report.data;
  return (
    <div className={styles.section}>
      <div className={`${styles.toolbar} ${styles.noPrint}`}>
        <PeriodFields
          from={from}
          to={to}
          onChange={(f, tt) => {
            setFrom(f);
            setTo(tt);
          }}
        />
      </div>
      {report.isPending ? (
        <RuledSkeleton rows={5} />
      ) : report.error || !data ? (
        <p className={styles.error}>{errorMessage(report.error)}</p>
      ) : (
        <>
          <div className={styles.titleRow}>
            <p className={styles.note}>
              {t("reports.periodLine", { from: formatDate(data.first), to: formatDate(data.last) })}
            </p>
            <ExportButtons path="/admin/reports/fill-rate" query={query} />
          </div>
          {data.rows.length === 0 ? (
            <EmptyState text={t("reports.empty")} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th scope="col">{t("reports.teacher")}</th>
                  <th scope="col">{t("reports.due")}</th>
                  <th scope="col">{t("reports.conducted")}</th>
                  <th scope="col">{t("reports.unfilled")}</th>
                  <th scope="col">{t("reports.overdue")}</th>
                  <th scope="col">{t("reports.noTopic")}</th>
                  <th scope="col">{t("reports.filled")}</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((row) => (
                  <tr key={row.teacher}>
                    <td>{row.teacher_name}</td>
                    <td className="mono">{row.due}</td>
                    <td className="mono">{row.conducted}</td>
                    <td className="mono">{row.unfilled}</td>
                    <td className={`mono ${row.overdue ? styles.error : ""}`}>{row.overdue}</td>
                    <td className="mono">{row.no_topic}</td>
                    <td className="mono">{num(row.filled_percent, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </>
      )}
    </div>
  );
}

/** «Отчёты» of the administrator (SPEC §8.8). */
export function AdminReportsPage() {
  const [tab, setTab] = useState<Tab>("performance");
  const tabs: [Tab, string][] = [
    ["performance", t("reports.tabPerformance")],
    ["fill", t("reports.tabFill")],
    ["statement", t("reports.statement")],
  ];
  return (
    <section className={styles.page}>
      <h1>{t("reports.title")}</h1>
      <div className={`${styles.tabs} ${styles.noPrint}`} role="tablist">
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
      {tab === "performance" && <PerformanceTab />}
      {tab === "fill" && <FillRateTab />}
      {tab === "statement" && <StatementPanel />}
    </section>
  );
}
