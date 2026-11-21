import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";

import { ExportButtons } from "@/features/reports/ExportButtons";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, type Schemas } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatDateTime } from "@/shared/lib/time";
import { Button, EmptyState, RuledSkeleton, SelectField, Table, TextField } from "@/shared/ui";

import { actionText, changes } from "./labels";

type AuditPage = Schemas["PaginatedAuditLogList"];
type LoginPage = Schemas["PaginatedLoginEventList"];
type Filters = Record<string, string>;

function Changes({ before, after }: { before: unknown; after: unknown }) {
  const rows = changes(before, after);
  if (rows.length === 0) return null;
  return (
    <details>
      <summary>{t("audit.details")}</summary>
      <Table>
        <thead>
          <tr>
            <th scope="col">{t("audit.field")}</th>
            <th scope="col">{t("audit.before")}</th>
            <th scope="col">{t("audit.after")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.field}>
              <td className="mono">{row.field}</td>
              <td className="mono">{row.before}</td>
              <td className="mono">{row.after}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </details>
  );
}

function EventsTab() {
  const [draft, setDraft] = useState<Filters>({});
  const [filters, setFilters] = useState<Filters>({});
  const [page, setPage] = useState(1);
  const query = { ...filters, page: String(page) };
  const events = useQuery({
    queryKey: ["admin", "audit", query],
    queryFn: () => api<AuditPage>("/admin/audit", { query }),
    placeholderData: keepPreviousData,
  });
  const field = (name: string, label: string, type = "text") => (
    <TextField
      label={label}
      type={type}
      value={draft[name] ?? ""}
      onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
    />
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const clean = Object.fromEntries(Object.entries(draft).filter(([, v]) => v.trim()));
    setFilters(clean);
    setPage(1);
  };
  return (
    <div className={styles.section}>
      <form className={styles.toolbar} onSubmit={submit} noValidate>
        {field("action", t("audit.action"))}
        {field("entity_type", t("audit.entity"))}
        {field("entity_id", t("audit.entityId"))}
        {field("date_from", t("audit.from"), "date")}
        {field("date_to", t("audit.to"), "date")}
        <Button type="submit" variant="primary">
          {t("audit.filter")}
        </Button>
        <Button
          onClick={() => {
            setDraft({});
            setFilters({});
            setPage(1);
          }}
        >
          {t("audit.reset")}
        </Button>
      </form>
      <ExportButtons path="/admin/audit/export" query={filters} print={false} />
      {events.isPending ? (
        <RuledSkeleton rows={6} />
      ) : events.error ? (
        <p className={styles.error}>{errorMessage(events.error)}</p>
      ) : events.data.results.length === 0 ? (
        <EmptyState text={t("audit.empty")} />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("audit.at")}</th>
                <th scope="col">{t("audit.actor")}</th>
                <th scope="col">{t("audit.action")}</th>
                <th scope="col">{t("audit.entity")}</th>
                <th scope="col">{t("audit.details")}</th>
              </tr>
            </thead>
            <tbody>
              {events.data.results.map((entry) => (
                <tr key={entry.id}>
                  <td className="mono">{formatDateTime(entry.at)}</td>
                  <td>
                    {entry.actor_name ?? t("audit.system")}
                    {entry.actor_role && (
                      <span className={styles.status}> · {entry.actor_role}</span>
                    )}
                    {entry.ip && <span className={styles.status}> · {entry.ip}</span>}
                  </td>
                  <td>
                    {actionText(entry.action)}
                    <span className={`${styles.status} mono`}> {entry.action}</span>
                  </td>
                  <td className="mono">
                    {entry.entity_type}
                    <span className={styles.status}> {entry.entity_id}</span>
                  </td>
                  <td>
                    {entry.reason && (
                      <p className={styles.note}>
                        {t("audit.reason")}: {entry.reason}
                      </p>
                    )}
                    <Changes before={entry.before} after={entry.after} />
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div className={styles.row}>
            <Button onClick={() => setPage(page - 1)} disabled={!events.data.previous}>
              {t("common.previous")}
            </Button>
            <Button onClick={() => setPage(page + 1)} disabled={!events.data.next}>
              {t("common.next")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

function LoginsTab() {
  const [login, setLogin] = useState("");
  const [success, setSuccess] = useState("");
  const [page, setPage] = useState(1);
  const query = {
    login: login.trim() || undefined,
    success: success || undefined,
    page: String(page),
  };
  const events = useQuery({
    queryKey: ["admin", "login-events", query],
    queryFn: () => api<LoginPage>("/admin/login-events", { query }),
    placeholderData: keepPreviousData,
  });
  return (
    <div className={styles.section}>
      <div className={styles.toolbar}>
        <TextField
          label={t("audit.login")}
          value={login}
          onChange={(e) => {
            setLogin(e.target.value);
            setPage(1);
          }}
        />
        <SelectField
          label={t("audit.result")}
          value={success}
          onChange={(e) => {
            setSuccess(e.target.value);
            setPage(1);
          }}
          options={[
            { value: "", label: t("audit.anyResult") },
            { value: "true", label: t("audit.success") },
            { value: "false", label: t("audit.failed") },
          ]}
        />
      </div>
      {events.isPending ? (
        <RuledSkeleton rows={6} />
      ) : events.error ? (
        <p className={styles.error}>{errorMessage(events.error)}</p>
      ) : events.data.results.length === 0 ? (
        <EmptyState text={t("audit.empty")} />
      ) : (
        <>
          <Table>
            <thead>
              <tr>
                <th scope="col">{t("audit.at")}</th>
                <th scope="col">{t("audit.login")}</th>
                <th scope="col">{t("audit.result")}</th>
                <th scope="col">{t("audit.ip")}</th>
              </tr>
            </thead>
            <tbody>
              {events.data.results.map((e) => (
                <tr key={e.id}>
                  <td className="mono">{formatDateTime(e.at)}</td>
                  <td className="mono">{e.login_attempted}</td>
                  <td className={e.success ? undefined : styles.error}>
                    {e.success ? t("audit.success") : t("audit.failed")}
                    <span className={`${styles.status} mono`}> {e.reason}</span>
                  </td>
                  <td className="mono">{e.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </Table>
          <div className={styles.row}>
            <Button onClick={() => setPage(page - 1)} disabled={!events.data.previous}>
              {t("common.previous")}
            </Button>
            <Button onClick={() => setPage(page + 1)} disabled={!events.data.next}>
              {t("common.next")}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

/** «Аудит» (SPEC §8.10): events with «было → стало», export, the login journal. */
export function AuditPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "logins" ? "logins" : "events";
  const tabs: [string, string][] = [
    ["events", t("audit.tabEvents")],
    ["logins", t("audit.tabLogins")],
  ];
  return (
    <section className={styles.page}>
      <h1>{t("audit.title")}</h1>
      <div className={styles.tabs} role="tablist">
        {tabs.map(([value, label]) => (
          <button
            key={value}
            type="button"
            role="tab"
            className={styles.tab}
            aria-selected={tab === value}
            onClick={() => setParams(value === "events" ? {} : { tab: value })}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "events" ? <EventsTab /> : <LoginsTab />}
    </section>
  );
}
