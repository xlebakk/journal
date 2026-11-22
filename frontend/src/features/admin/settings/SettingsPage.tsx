import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { useReauth } from "@/features/auth/reauthContext";
import styles from "@/features/schedule/SchedulePage.module.css";
import { api, upload, type Schemas } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t, type MessageKey } from "@/shared/i18n";
import { formatDateTime } from "@/shared/lib/time";
import { Button, Checkbox, FileField, RuledSkeleton, SelectField, TextField } from "@/shared/ui";

type Settings = Schemas["CenterSettings"];
type NumberField = keyof Settings &
  `${string}_${"threshold" | "minutes" | "hours" | "days" | "lesson" | "percent"}`;

const SECURITY: NumberField[] = [
  "lockout_threshold",
  "lockout_base_minutes",
  "lockout_max_hours",
  "admin_idle_minutes",
  "admin_absolute_hours",
  "teacher_idle_minutes",
  "teacher_absolute_hours",
  "teacher_remember_days",
  "student_absolute_hours",
  "student_remember_days",
];
const JOURNAL: NumberField[] = [
  "edit_window_days",
  "max_grades_per_lesson",
  "low_grade_percent",
  "attendance_threshold_percent",
  "attendance_window_days",
];
const KEY = ["admin", "settings"];
const READ_ONLY = [
  "logo",
  "last_backup_at",
  "last_backup_ok",
  "last_restore_check_at",
  "last_restore_check_ok",
  "updated_at",
];

function restoreText(s: Settings): string {
  if (!s.last_restore_check_at) return t("settings.restoreNone");
  const date = formatDateTime(s.last_restore_check_at);
  return s.last_restore_check_ok
    ? t("settings.restoreOk", { date })
    : t("settings.restoreFailed", { date });
}

function backupText(s: Settings): string {
  if (!s.last_backup_at) return t("settings.backupNone");
  const date = formatDateTime(s.last_backup_at);
  return s.last_backup_ok ? t("settings.backupOk", { date }) : t("settings.backupFailed", { date });
}

function SettingsForm({ initial }: { initial: Settings }) {
  const queryClient = useQueryClient();
  const withReauth = useReauth();
  const [draft, setDraft] = useState<Settings>(initial);
  const save = useMutation({
    mutationFn: () => {
      const body = Object.fromEntries(
        Object.entries(draft).filter(([key]) => !READ_ONLY.includes(key)),
      );
      return withReauth(() => api<Settings>("/admin/settings", { method: "PATCH", body }));
    },
    onSuccess: (next) => {
      queryClient.setQueryData(KEY, next);
      void queryClient.invalidateQueries({ queryKey: ["branding"] });
    },
  });
  const number = (name: NumberField) => (
    <TextField
      key={name}
      label={t(`settings.${name}` as MessageKey)}
      type="number"
      inputMode="numeric"
      value={draft[name] ?? ""}
      onChange={(e) => setDraft({ ...draft, [name]: Number(e.target.value) })}
      error={fieldError(save.error, name)}
    />
  );
  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <h2>{t("settings.center")}</h2>
      <TextField
        label={t("settings.centerName")}
        value={draft.center_name ?? ""}
        onChange={(e) => setDraft({ ...draft, center_name: e.target.value })}
        error={fieldError(save.error, "center_name")}
      />
      <TextField
        label={t("settings.contacts")}
        value={draft.contacts ?? ""}
        onChange={(e) => setDraft({ ...draft, contacts: e.target.value })}
      />
      <TextField
        label={t("settings.siteUrl")}
        value={draft.site_url ?? ""}
        onChange={(e) => setDraft({ ...draft, site_url: e.target.value })}
        error={fieldError(save.error, "site_url")}
      />
      <h2>{t("settings.journal")}</h2>
      <div className={styles.grid}>{JOURNAL.map(number)}</div>
      <SelectField
        label={t("settings.default_grade_scale")}
        value={draft.default_grade_scale}
        onChange={(e) =>
          setDraft({
            ...draft,
            default_grade_scale: e.target.value as Settings["default_grade_scale"],
          })
        }
        options={[
          { value: "100", label: t("settings.scale100") },
          { value: "5", label: t("settings.scale5") },
          { value: "10", label: t("settings.scale10") },
        ]}
      />
      <h2>{t("settings.security")}</h2>
      <div className={styles.grid}>{SECURITY.map(number)}</div>
      <Checkbox
        label={t("settings.require_admin_2fa")}
        checked={draft.require_admin_2fa ?? false}
        onChange={(e) => setDraft({ ...draft, require_admin_2fa: e.target.checked })}
      />
      <Checkbox
        label={t("settings.require_teacher_2fa")}
        checked={draft.require_teacher_2fa ?? false}
        onChange={(e) => setDraft({ ...draft, require_teacher_2fa: e.target.checked })}
      />
      <p className={styles.note}>{t("settings.reauthNote")}</p>
      {save.error && !Object.keys(draft).some((k) => fieldError(save.error, k)) && (
        <p className={styles.error} role="alert">
          {errorMessage(save.error)}
        </p>
      )}
      {save.isSuccess && (
        <p className={styles.success} role="status">
          {t("settings.saved")}
        </p>
      )}
      <p>
        <Button type="submit" variant="primary" disabled={save.isPending}>
          {t("settings.save")}
        </Button>
      </p>
    </form>
  );
}

function LogoBlock({ logo }: { logo: string | null }) {
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const done = (next: Settings) => {
    queryClient.setQueryData(KEY, next);
    void queryClient.invalidateQueries({ queryKey: ["branding"] });
  };
  const send = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (file) form.append("file", file);
      return upload<Settings>("/admin/settings/logo", form);
    },
    onSuccess: done,
  });
  const remove = useMutation({
    mutationFn: () => api<Settings>("/admin/settings/logo", { method: "DELETE" }),
    onSuccess: done,
  });
  return (
    <section className={styles.section} aria-labelledby="settings-logo">
      <h2 id="settings-logo">{t("settings.logo")}</h2>
      {logo ? (
        <img src={logo} alt={t("settings.logo")} className={styles.logo} />
      ) : (
        <p className={styles.note}>{t("settings.noLogo")}</p>
      )}
      <FileField
        label={t("settings.logo")}
        hint={t("settings.logoHint")}
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        error={fieldError(send.error, "file")}
      />
      <div className={styles.row}>
        <Button onClick={() => send.mutate()} disabled={!file || send.isPending}>
          {t("settings.logoUpload")}
        </Button>
        {logo && (
          <Button onClick={() => remove.mutate()} disabled={remove.isPending}>
            {t("settings.logoDelete")}
          </Button>
        )}
      </div>
    </section>
  );
}

/** «Настройки» (SPEC §2, §8.11). */
export function SettingsPage() {
  const settings = useQuery({ queryKey: KEY, queryFn: () => api<Settings>("/admin/settings") });
  if (settings.isPending) return <RuledSkeleton rows={8} />;
  if (settings.error || !settings.data) {
    return <p className={styles.error}>{errorMessage(settings.error)}</p>;
  }
  return (
    <section className={styles.page}>
      <h1>{t("settings.title")}</h1>
      <LogoBlock logo={settings.data.logo} />
      <SettingsForm key={settings.data.updated_at} initial={settings.data} />
      <section className={styles.section} aria-labelledby="settings-backup">
        <h2 id="settings-backup">{t("settings.backup")}</h2>
        <p className={settings.data.last_backup_ok === false ? styles.error : styles.note}>
          {backupText(settings.data)}
        </p>
        <p className={settings.data.last_restore_check_ok === false ? styles.error : styles.note}>
          {restoreText(settings.data)}
        </p>
      </section>
    </section>
  );
}
