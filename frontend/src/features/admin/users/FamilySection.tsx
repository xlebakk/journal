import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api, type Schemas } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import {
  Button,
  Checkbox,
  EmptyState,
  PasswordField,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import { useUsers, type UserDetail } from "./api";
import styles from "./Users.module.css";

type Member = Schemas["FamilyMember"];
type Added = Schemas["ParentAdded"];

function FamilyTable({ rows, onRemove }: { rows: Member[]; onRemove?: (row: Member) => void }) {
  return (
    <Table>
      <thead>
        <tr>
          <th scope="col">{t("users.name")}</th>
          <th scope="col">{t("users.login")}</th>
          {onRemove && (
            <th scope="col">
              <span className="visually-hidden">{t("common.actions")}</span>
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>
              <Link to={`/admin/users/${row.id}`}>{row.full_name}</Link>
              {!row.is_active && (
                <span className={styles.muted}> · {t("users.statusBlocked")}</span>
              )}
            </td>
            <td className="mono">{row.login}</td>
            {onRemove && (
              <td>
                <Button variant="danger" onClick={() => onRemove(row)}>
                  {t("family.unlink")}
                </Button>
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Splits «Алиева Гульнора Рустамовна» from the student profile into the form fields. */
function nameParts(full: string): { last: string; first: string; middle: string } {
  const [last = "", first = "", ...rest] = full.trim().split(/\s+/);
  return { last, first, middle: rest.join(" ") };
}

/** «Родители» in a student's card (stage 14): a new parent account or an existing one. */
export function ParentsSection({ student }: { student: UserDetail }) {
  const queryClient = useQueryClient();
  const key = ["admin", "users", "parents", student.id];
  const parents = useQuery({
    queryKey: key,
    queryFn: () => api<Member[]>(`/admin/users/${student.id}/parents`),
  });
  const guess = nameParts(student.student_profile?.parent_name ?? "");
  const [mode, setMode] = useState<"new" | "existing">("new");
  const [form, setForm] = useState({
    last_name: guess.last,
    first_name: guess.first,
    middle_name: guess.middle,
  });
  const [search, setSearch] = useState("");
  const [existing, setExisting] = useState("");
  const [password, setPassword] = useState("");
  const [mustChange, setMustChange] = useState(false);
  const candidates = useUsers({ q: search, role: "parent", status: "", page: 1 });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
  const add = useMutation({
    mutationFn: () =>
      api<Added>(`/admin/users/${student.id}/parents`, {
        method: "POST",
        body:
          mode === "existing"
            ? { existing }
            : { ...form, password, must_change_password: mustChange },
      }),
    onSuccess: async () => {
      setExisting("");
      setPassword("");
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (row: Member) =>
      api<void>(`/admin/users/${student.id}/parents/${row.id}`, { method: "DELETE" }),
    onSuccess: refresh,
  });

  return (
    <section className={styles.page} aria-labelledby="user-parents">
      <h2 id="user-parents">{t("family.parents")}</h2>
      <p className={styles.note}>{t("family.parentsHint")}</p>
      {parents.data && parents.data.length > 0 ? (
        <FamilyTable rows={parents.data} onRemove={(row) => remove.mutate(row)} />
      ) : (
        parents.data && <EmptyState text={t("family.noParents")} />
      )}
      <div className={styles.form}>
        <SelectField
          label={t("family.addHow")}
          value={mode}
          onChange={(e) => setMode(e.target.value as "new" | "existing")}
          options={[
            { value: "new", label: t("family.addNew") },
            { value: "existing", label: t("family.addExisting") },
          ]}
        />
        {mode === "new" ? (
          <div className={styles.grid}>
            <TextField
              label={t("userForm.lastName")}
              value={form.last_name}
              onChange={(e) => setForm({ ...form, last_name: e.target.value })}
              error={fieldError(add.error, "last_name")}
            />
            <TextField
              label={t("userForm.firstName")}
              value={form.first_name}
              onChange={(e) => setForm({ ...form, first_name: e.target.value })}
            />
            <TextField
              label={t("userForm.middleName")}
              value={form.middle_name}
              onChange={(e) => setForm({ ...form, middle_name: e.target.value })}
            />
            <PasswordField
              label={t("userForm.password")}
              hint={t("password.hint")}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={fieldError(add.error, "password")}
            />
            <Checkbox
              label={t("userForm.mustChange")}
              checked={mustChange}
              onChange={(e) => setMustChange(e.target.checked)}
            />
          </div>
        ) : (
          <div className={styles.grid}>
            <TextField
              label={t("users.search")}
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <SelectField
              label={t("family.parent")}
              value={existing}
              onChange={(e) => setExisting(e.target.value)}
              options={[
                { value: "", label: "—" },
                ...(candidates.data?.results ?? []).map((u) => ({
                  value: u.id,
                  label: `${u.full_name} · ${u.login}`,
                })),
              ]}
            />
          </div>
        )}
        <div className={styles.actions}>
          <Button
            variant="primary"
            disabled={
              add.isPending ||
              (mode === "existing" ? !existing : !form.last_name.trim() || password.length < 10)
            }
            onClick={() => add.mutate()}
          >
            {t("family.add")}
          </Button>
        </div>
        {(add.error ?? remove.error) && (
          <p className={styles.error} role="alert">
            {fieldError(add.error, "existing") ?? errorMessage(add.error ?? remove.error)}
          </p>
        )}
      </div>
    </section>
  );
}

/** «Дети» in a parent's card. */
export function ChildrenSection({ parentId }: { parentId: string }) {
  const children = useQuery({
    queryKey: ["admin", "users", "children", parentId],
    queryFn: () => api<Member[]>(`/admin/users/${parentId}/children`),
  });
  return (
    <section className={styles.page} aria-labelledby="user-children">
      <h2 id="user-children">{t("family.children")}</h2>
      {children.error && <p className={styles.error}>{errorMessage(children.error)}</p>}
      {children.data &&
        (children.data.length > 0 ? (
          <FamilyTable rows={children.data} />
        ) : (
          <EmptyState text={t("family.noChildren")} />
        ))}
    </section>
  );
}
