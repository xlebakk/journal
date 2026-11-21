import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { errorMessage } from "@/shared/api/errors";
import { formatDateTime as when } from "@/shared/lib/time";
import { t } from "@/shared/i18n";
import { Button, EmptyState, RuledSkeleton, SelectField, Table, TextField } from "@/shared/ui";

import { useUsers } from "./api";
import { statusLabel } from "./labels";
import styles from "./Users.module.css";

const ROLE_OPTIONS = [
  { value: "", label: t("users.any") },
  { value: "admin", label: t("roles.admin") },
  { value: "teacher", label: t("roles.teacher") },
  { value: "student", label: t("roles.student") },
];
const STATUS_OPTIONS = [
  { value: "", label: t("users.any") },
  { value: "active", label: t("users.statusActive") },
  { value: "blocked", label: t("users.statusBlocked") },
  { value: "archived", label: t("users.statusArchived") },
];

/** Filters live in the URL, so the list survives reloads and back navigation. */
export function UsersPage() {
  const [params, setParams] = useSearchParams();
  const role = params.get("role") ?? "";
  const status = params.get("status") ?? "";
  const page = Number(params.get("page") ?? "1") || 1;
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

  const users = useUsers({ q: debounced, role, status, page });

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries({ ...changes, page: changes.page ?? "" })) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    setParams(next, { replace: true });
  };

  useEffect(() => {
    if ((params.get("q") ?? "") !== debounced) update({ q: debounced });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync only when the search settles
  }, [debounced]);

  const data = users.data;
  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("users.title")}</h1>
        <Link className={styles.primaryLink} to="/admin/users/new">
          {t("users.create")}
        </Link>
      </div>

      <div className={styles.filters}>
        <TextField
          label={t("users.search")}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className={styles.search}
        />
        <SelectField
          label={t("users.role")}
          options={ROLE_OPTIONS}
          value={role}
          onChange={(e) => update({ role: e.target.value })}
        />
        <SelectField
          label={t("users.status")}
          options={STATUS_OPTIONS}
          value={status}
          onChange={(e) => update({ status: e.target.value })}
        />
      </div>

      {users.isPending ? (
        <RuledSkeleton rows={8} />
      ) : users.error ? (
        <p className={styles.error}>{errorMessage(users.error)}</p>
      ) : data && data.results.length === 0 ? (
        <EmptyState text={t("users.empty")} />
      ) : (
        data && (
          <>
            <div className={styles.tableWrap}>
              <Table>
                <thead>
                  <tr>
                    <th scope="col">{t("users.name")}</th>
                    <th scope="col">{t("users.login")}</th>
                    <th scope="col">{t("users.roles")}</th>
                    <th scope="col">{t("users.status")}</th>
                    <th scope="col">{t("users.twoFactor")}</th>
                    <th scope="col">{t("users.lastLogin")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((user) => (
                    <tr key={user.id}>
                      <td>
                        <Link to={`/admin/users/${user.id}`}>{user.full_name}</Link>
                      </td>
                      <td className="mono">{user.login}</td>
                      <td>{user.roles.map((r) => t(`roles.${r}`)).join(", ")}</td>
                      <td className={user.status === "active" ? undefined : styles.muted}>
                        {statusLabel(user.status)}
                      </td>
                      <td>{user.totp_enabled ? t("common.yes") : t("common.no")}</td>
                      <td className="mono">
                        {user.last_login ? when(user.last_login) : t("users.never")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
            <div className={styles.pager}>
              <span>{t("users.shown", { shown: data.results.length, total: data.count })}</span>
              <Button disabled={!data.previous} onClick={() => update({ page: String(page - 1) })}>
                {t("common.previous")}
              </Button>
              <Button disabled={!data.next} onClick={() => update({ page: String(page + 1) })}>
                {t("common.next")}
              </Button>
            </div>
          </>
        )
      )}
    </section>
  );
}
