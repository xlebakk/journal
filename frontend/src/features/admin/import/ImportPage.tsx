import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import styles from "@/features/schedule/SchedulePage.module.css";
import { download, upload, type Schemas } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, tMaybe, type MessageKey } from "@/shared/i18n";
import { Button, EmptyState, FileField, Table } from "@/shared/ui";

import { CardsSheet } from "./CardsSheet";

type ImportResult = Schemas["StudentImportResult"];

/** «login:login_taken» → «Логин: логин занят». */
function issueText(issue: string): string {
  const [field, code] = issue.includes(":") ? issue.split(":", 2) : ["", issue];
  const text = tMaybe(`errors.${code}`) ?? code ?? issue;
  if (!field) return text;
  return `${t(`importStudents.fields.${field}` as MessageKey)}: ${text}`;
}

/** «Импорт учеников» (SPEC §8.2): template → preview with errors per line → one transaction. */
export function ImportPage() {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const send = useMutation({
    mutationFn: (apply: boolean) => {
      const form = new FormData();
      if (file) form.append("file", file);
      if (apply) form.append("apply", "true");
      return upload<ImportResult>("/admin/import/students", form);
    },
    onSuccess: async (result) => {
      if (result.applied) await queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });
  const template = useMutation({ mutationFn: () => download("/admin/import/students/template") });
  const result = send.data;
  const errors = result?.rows.filter((r) => r.issues.length > 0).length ?? 0;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    send.mutate(false);
  };
  const again = () => {
    send.reset();
    setFile(null);
    setInputKey((k) => k + 1);
  };

  if (result?.applied) {
    return (
      <section className={styles.page}>
        <div className={`${styles.titleRow} ${styles.noPrint}`}>
          <h1>{t("importStudents.cards")}</h1>
          <div className={styles.row}>
            <Button variant="primary" onClick={() => window.print()}>
              {t("importStudents.printCards")}
            </Button>
            <Button onClick={again}>{t("importStudents.again")}</Button>
          </div>
        </div>
        <p className={`${styles.success} ${styles.noPrint}`} role="status">
          {t("importStudents.created", { count: result.created.length })}
        </p>
        <CardsSheet cards={result.created} />
      </section>
    );
  }

  return (
    <section className={styles.page}>
      <div className={styles.titleRow}>
        <h1>{t("importStudents.title")}</h1>
        <Button onClick={() => template.mutate()} disabled={template.isPending}>
          {t("importStudents.template")}
        </Button>
      </div>
      <p className={styles.note}>{t("importStudents.hint")}</p>
      <form className={styles.form} onSubmit={submit} noValidate>
        <FileField
          key={inputKey}
          label={t("importStudents.file")}
          accept=".xlsx,.csv"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            send.reset();
          }}
          error={fieldError(send.error, "file")}
        />
        <div className={styles.row}>
          <Button type="submit" disabled={!file || send.isPending}>
            {t("importStudents.preview")}
          </Button>
          {result && errors === 0 && result.rows.length > 0 && (
            <Button variant="primary" onClick={() => send.mutate(true)} disabled={send.isPending}>
              {t("importStudents.apply")}
            </Button>
          )}
        </div>
        {(send.error && !fieldError(send.error, "file")) || template.error ? (
          <p className={styles.error} role="alert">
            {errorMessage(send.error ?? template.error)}
          </p>
        ) : null}
      </form>
      {result && (
        <>
          <p className={styles.note}>
            {t("importStudents.rows", { count: result.rows.length, errors })}
            {errors > 0 && <> {t("importStudents.fixFirst")}</>}
          </p>
          {result.rows.length === 0 ? (
            <EmptyState text={t("errors.empty_file")} />
          ) : (
            <Table>
              <thead>
                <tr>
                  <th scope="col">{t("importStudents.line")}</th>
                  <th scope="col">{t("importStudents.name")}</th>
                  <th scope="col">{t("importStudents.login")}</th>
                  <th scope="col">{t("importStudents.group")}</th>
                  <th scope="col">{t("importStudents.issues")}</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.line}>
                    <td className="mono">{row.line}</td>
                    <td>
                      {[row.last_name, row.first_name, row.middle_name].filter(Boolean).join(" ") ||
                        "—"}
                    </td>
                    <td className="mono">
                      {row.login || (
                        <span className={styles.status}>{t("importStudents.autoLogin")}</span>
                      )}
                    </td>
                    <td>{row.group_name || "—"}</td>
                    <td className={row.issues.length ? styles.error : styles.status}>
                      {row.issues.length
                        ? row.issues.map(issueText).join("; ")
                        : t("importStudents.ok")}
                      {row.warnings.length > 0 && (
                        <span className={styles.status}>
                          {" "}
                          · {row.warnings.map(issueText).join("; ")}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </>
      )}
    </section>
  );
}
