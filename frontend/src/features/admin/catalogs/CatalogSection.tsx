import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
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

import styles from "./Catalogs.module.css";

export type Row = { id: string } & Record<string, unknown>;
type Value = string | boolean;

export type FieldDef = {
  name: string;
  label: MessageKey;
  kind: "text" | "number" | "decimal" | "date" | "checkbox" | "select";
  options?: { value: string; label: string }[];
  /** Shown in the table; defaults to the raw value. */
  render?: (row: Row) => string;
  required?: boolean;
};

export type CatalogConfig = {
  endpoint: string;
  title: MessageKey;
  fields: FieldDef[];
  query?: Record<string, string | undefined>;
  /** Values for a new row (e.g. the selected year for terms). */
  defaults?: Record<string, Value>;
  name: (row: Row) => string;
};

function toForm(fields: FieldDef[], row: Row | null, defaults: Record<string, Value> = {}) {
  const values: Record<string, Value> = {};
  for (const field of fields) {
    const raw = row ? row[field.name] : defaults[field.name];
    values[field.name] = field.kind === "checkbox" ? Boolean(raw) : raw == null ? "" : String(raw);
  }
  return values;
}

function toPayload(fields: FieldDef[], values: Record<string, Value>) {
  const payload: Record<string, unknown> = {};
  for (const field of fields) {
    const value = values[field.name];
    if (field.kind === "checkbox") payload[field.name] = Boolean(value);
    else if (field.kind === "number") payload[field.name] = value === "" ? null : Number(value);
    else if (field.kind === "select" || field.kind === "date")
      payload[field.name] = value === "" ? null : value;
    else payload[field.name] = typeof value === "string" ? value.trim() : value;
  }
  return payload;
}

function display(field: FieldDef, row: Row): string {
  if (field.render) return field.render(row);
  const value = row[field.name];
  if (field.kind === "checkbox") return value ? t("common.yes") : t("common.no");
  if (field.kind === "select") {
    return field.options?.find((o) => o.value === value)?.label ?? "—";
  }
  return value == null || value === "" ? "—" : String(value);
}

/** A catalog: ruled table, add/edit in a dialog, delete refused with «in use» (SPEC §8.4). */
export function CatalogSection({ config }: { config: CatalogConfig }) {
  const queryClient = useQueryClient();
  const key = ["admin", "catalog", config.endpoint, config.query ?? {}];
  const rows = useQuery({
    queryKey: key,
    queryFn: () => api<Row[]>(config.endpoint, { query: config.query }),
  });
  const [editing, setEditing] = useState<Row | "new" | null>(null);
  const [values, setValues] = useState<Record<string, Value>>({});
  const [deleting, setDeleting] = useState<Row | null>(null);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["admin"] });
  const save = useMutation({
    mutationFn: () => {
      const body = toPayload(config.fields, values);
      return editing === "new"
        ? api<Row>(config.endpoint, { method: "POST", body })
        : api<Row>(`${config.endpoint}/${(editing as Row).id}`, { method: "PATCH", body });
    },
    onSuccess: async () => {
      setEditing(null);
      await refresh();
    },
  });
  const remove = useMutation({
    mutationFn: (row: Row) => api<void>(`${config.endpoint}/${row.id}`, { method: "DELETE" }),
    onSuccess: async () => {
      setDeleting(null);
      await refresh();
    },
  });

  const open = (row: Row | "new") => {
    save.reset();
    setValues(toForm(config.fields, row === "new" ? null : row, config.defaults));
    setEditing(row);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  const formError =
    save.error instanceof ApiError && (save.error.code || save.error.fields.non_field_errors)
      ? (fieldError(save.error, "non_field_errors") ?? errorMessage(save.error))
      : null;

  return (
    <section className={styles.section} aria-label={t(config.title)}>
      <div className={styles.head}>
        <h2>{t(config.title)}</h2>
        <Button onClick={() => open("new")}>{t("catalogs.add")}</Button>
      </div>
      {rows.isPending ? (
        <RuledSkeleton rows={3} />
      ) : rows.error ? (
        <p className={styles.error}>{errorMessage(rows.error)}</p>
      ) : rows.data.length === 0 ? (
        <EmptyState text={t("catalogs.empty")} />
      ) : (
        <div className={styles.tableWrap}>
          <Table>
            <thead>
              <tr>
                {config.fields.map((f) => (
                  <th key={f.name} scope="col">
                    {t(f.label)}
                  </th>
                ))}
                <th scope="col">
                  <span className="visually-hidden">{t("catalogs.edit")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.data.map((row) => (
                <tr key={row.id}>
                  {config.fields.map((f) => (
                    <td key={f.name} className={f.kind === "text" ? undefined : "mono"}>
                      {display(f, row)}
                    </td>
                  ))}
                  <td className={styles.actions}>
                    <Button onClick={() => open(row)}>{t("catalogs.edit")}</Button>
                    <Button variant="danger" onClick={() => setDeleting(row)}>
                      {t("catalogs.delete")}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}

      <Dialog
        open={editing !== null}
        onOpenChange={(o) => !o && setEditing(null)}
        title={`${t(config.title)}: ${editing === "new" ? t("catalogs.add") : t("catalogs.edit")}`}
      >
        <form className={styles.form} onSubmit={submit} noValidate>
          {config.fields.map((f) => {
            const error = fieldError(save.error, f.name);
            const set = (value: Value) => setValues((v) => ({ ...v, [f.name]: value }));
            if (f.kind === "checkbox") {
              return (
                <Checkbox
                  key={f.name}
                  label={t(f.label)}
                  checked={Boolean(values[f.name])}
                  onChange={(e) => set(e.target.checked)}
                />
              );
            }
            if (f.kind === "select") {
              return (
                <SelectField
                  key={f.name}
                  label={t(f.label)}
                  value={String(values[f.name] ?? "")}
                  onChange={(e) => set(e.target.value)}
                  options={[{ value: "", label: "—" }, ...(f.options ?? [])]}
                  error={error}
                />
              );
            }
            return (
              <TextField
                key={f.name}
                label={t(f.label)}
                type={f.kind === "date" ? "date" : "text"}
                inputMode={f.kind === "number" || f.kind === "decimal" ? "decimal" : undefined}
                value={String(values[f.name] ?? "")}
                onChange={(e) => set(e.target.value)}
                error={error}
                required={f.required}
              />
            );
          })}
          {formError && (
            <p className={styles.error} role="alert">
              {formError}
            </p>
          )}
          <DialogActions>
            <Button type="submit" variant="primary" disabled={save.isPending}>
              {t("common.save")}
            </Button>
            <Button onClick={() => setEditing(null)}>{t("common.cancel")}</Button>
          </DialogActions>
        </form>
      </Dialog>

      <Dialog
        open={deleting !== null}
        onOpenChange={(o) => {
          if (!o) {
            setDeleting(null);
            remove.reset();
          }
        }}
        title={t("catalogs.delete")}
        description={deleting ? t("catalogs.deleteConfirm", { name: config.name(deleting) }) : ""}
      >
        {remove.error && (
          <p className={styles.error} role="alert">
            {errorMessage(remove.error)}
          </p>
        )}
        <DialogActions>
          <Button
            variant="primary"
            disabled={remove.isPending}
            onClick={() => deleting && remove.mutate(deleting)}
          >
            {t("catalogs.delete")}
          </Button>
          <Button onClick={() => setDeleting(null)}>{t("common.cancel")}</Button>
        </DialogActions>
      </Dialog>
    </section>
  );
}
