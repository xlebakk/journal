import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import styles from "@/features/schedule/SchedulePage.module.css";
import { api } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  RuledSkeleton,
  SelectField,
  Table,
  TextField,
} from "@/shared/ui";

import { useGroups, useInvalidateAdmin, useYears, type Group } from "./api";

function CreateGroupDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const years = useYears();
  const navigate = useNavigate();
  const invalidate = useInvalidateAdmin();
  const current = years.data?.find((y) => y.is_current)?.id ?? years.data?.[0]?.id ?? "";
  const [name, setName] = useState("");
  const [level, setLevel] = useState("");
  const [year, setYear] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api<Group>("/admin/groups", {
        method: "POST",
        body: { name: name.trim(), level: level.trim(), academic_year: year || current },
      }),
    onSuccess: async (group) => {
      await invalidate();
      navigate(`/admin/groups/${group.id}`);
    },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate();
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()} title={t("groups.create")}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <TextField
          label={t("groups.name")}
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={fieldError(create.error, "name")}
        />
        <TextField
          label={t("groups.level")}
          value={level}
          onChange={(e) => setLevel(e.target.value)}
        />
        <SelectField
          label={t("groups.year")}
          value={year || current}
          onChange={(e) => setYear(e.target.value)}
          options={(years.data ?? []).map((y) => ({ value: y.id, label: y.name }))}
        />
        {create.error && !fieldError(create.error, "name") && (
          <p className={styles.error} role="alert">
            {fieldError(create.error, "non_field_errors") ?? errorMessage(create.error)}
          </p>
        )}
        <DialogActions>
          <Button type="submit" variant="primary" disabled={create.isPending || !name.trim()}>
            {t("groups.create")}
          </Button>
          <Button onClick={onClose}>{t("common.cancel")}</Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

/** «Группы» (SPEC §8.3). */
export function GroupsPage() {
  const [archived, setArchived] = useState(false);
  const groups = useGroups(archived);
  const [creating, setCreating] = useState(false);
  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("groups.title")}</h1>
        <Button variant="primary" onClick={() => setCreating(true)}>
          {t("groups.create")}
        </Button>
      </div>
      <Checkbox
        label={t("groups.showArchived")}
        checked={archived}
        onChange={(e) => setArchived(e.target.checked)}
      />
      {groups.isPending ? (
        <RuledSkeleton rows={4} />
      ) : groups.error ? (
        <p className={styles.error}>{errorMessage(groups.error)}</p>
      ) : groups.data.length === 0 ? (
        <EmptyState text={t("groups.empty")} />
      ) : (
        <Table>
          <thead>
            <tr>
              <th scope="col">{t("groups.name")}</th>
              <th scope="col">{t("groups.year")}</th>
              <th scope="col">{t("groups.level")}</th>
              <th scope="col">{t("groups.members")}</th>
              <th scope="col">{t("groups.courses")}</th>
            </tr>
          </thead>
          <tbody>
            {groups.data.map((group) => (
              <tr key={group.id}>
                <td>
                  <Link to={`/admin/groups/${group.id}`}>{group.name}</Link>
                  {group.is_archived && (
                    <span className={styles.status}> · {t("groups.archived")}</span>
                  )}
                </td>
                <td>{group.year_name}</td>
                <td>{group.level || "—"}</td>
                <td className="mono">{group.members_count}</td>
                <td>{group.courses.map((c) => c.subject_short).join(", ") || "—"}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <CreateGroupDialog open={creating} onClose={() => setCreating(false)} />
    </section>
  );
}
