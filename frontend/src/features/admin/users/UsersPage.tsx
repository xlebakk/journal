import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { errorMessage } from "@/shared/api/errors";
import { formatDateTime as when } from "@/shared/lib/time";
import { t } from "@/shared/i18n";
import { useSubjects } from "@/features/admin/groups/api";
import {
  Button,
  EmptyState,
  RuledSkeleton,
  Segmented,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import { useUsers } from "./api";
import { statusLabel } from "./labels";
import styles from "./Users.module.css";

// Stage 19: one tab per kind of person; «Персонал» is the administrators.
type Tab = "" | "student" | "teacher" | "parent" | "admin";
const TABS: { value: Tab; label: string }[] = [
  { value: "", label: t("users.tabAll") },
  { value: "student", label: t("users.tabStudents") },
  { value: "teacher", label: t("users.tabTeachers") },
  { value: "parent", label: t("users.tabParents") },
  { value: "admin", label: t("users.tabStaff") },
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
  const rawRole = params.get("role") ?? "";
  const role: Tab = TABS.some((tab) => tab.value === rawRole) ? (rawRole as Tab) : "";
  const subject = role === "teacher" ? (params.get("subject") ?? "") : "";
  const subjects = useSubjects();
  const status = params.get("status") ?? "";
  const page = Number(params.get("page") ?? "1") || 1;
  const [q, setQ] = useState(params.get("q") ?? "");
  const [debounced, setDebounced] = useState(q);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(q), 300);
    return () => clearTimeout(timer);
  }, [q]);

  const navigate = useNavigate();
  const [chosen, setChosen] = useState<string | null>(null);
  const users = useUsers({ q: debounced, role, status, page, subject });

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
        <div className={styles.actions}>
          {/* Stage 19: a row picked in the table opens for editing here. */}
          <Button
            disabled={!chosen}
            onClick={() => chosen && navigate(`/admin/users/${chosen}`)}
            title={chosen ? undefined : t("users.pickToEdit")}
          >
            {t("users.edit")}
          </Button>
          <Link className={styles.primaryLink} to="/admin/users/new">
            {t("users.create")}
          </Link>
        </div>
      </div>

      <Segmented
        label={t("users.title")}
        value={role}
        onChange={(value) => update({ role: value, subject: "" })}
        options={TABS}
      />

      <div className={styles.filters}>
        <TextField
          label={t("users.search")}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className={styles.search}
        />
        {role === "teacher" && (
          <SelectField
            label={t("users.subject")}
            options={[
              { value: "", label: t("users.anySubject") },
              ...(subjects.data ?? [])
                .filter((x) => !x.is_archived)
                .map((x) => ({ value: x.id, label: x.name })),
            ]}
            value={subject}
            onChange={(e) => update({ subject: e.target.value })}
          />
        )}
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
                    {role === "" && <th scope="col">{t("users.roles")}</th>}
                    {role === "teacher" && <th scope="col">{t("users.subjects")}</th>}
                    {role === "admin" && <th scope="col">{t("users.position")}</th>}
                    <th scope="col">{t("users.status")}</th>
                    <th scope="col">
                      <abbr title={t("users.twoFactorHint")}>{t("users.twoFactor")}</abbr>
                    </th>
                    <th scope="col">{t("users.lastLogin")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((user) => (
                    <tr
                      key={user.id}
                      className={user.id === chosen ? styles.chosenRow : styles.pickRow}
                      aria-selected={user.id === chosen}
                      onClick={() => setChosen(user.id)}
                      onDoubleClick={() => navigate(`/admin/users/${user.id}`)}
                    >
                      <td>
                        <Link to={`/admin/users/${user.id}`}>{user.full_name}</Link>
                      </td>
                      <td className="mono">{user.login}</td>
                      {role === "" && <td>{user.roles.map((r) => t(`roles.${r}`)).join(", ")}</td>}
                      {role === "teacher" && <td>{user.subjects.join(", ") || "—"}</td>}
                      {role === "admin" && (
                        <td>
                          {user.position ||
                            (user.is_superadmin ? t("roles.superadmin") : t("roles.admin"))}
                        </td>
                      )}
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
