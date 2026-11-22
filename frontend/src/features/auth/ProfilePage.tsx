import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";

import { api } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { useTheme } from "@/shared/lib/theme";
import { Button, LanguageSwitch, ThemeSwitch } from "@/shared/ui";

import { useStudentProfile } from "@/features/student/api";

import { ME_KEY, useMe } from "./api";
import styles from "./AccountPages.module.css";
import { CalendarSection } from "./CalendarSection";
import { useReauth } from "./reauthContext";
import { BackupCodes } from "./TotpSetupPage";

export function ProfilePage() {
  const me = useMe();
  const [theme, setTheme] = useTheme();
  const withReauth = useReauth();
  const queryClient = useQueryClient();
  const [codes, setCodes] = useState<string[] | null>(null);
  const student = useStudentProfile(me.data?.active_role === "student");

  const disable = useMutation({
    mutationFn: () => withReauth(() => api<void>("/auth/totp/setup", { method: "DELETE" })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ME_KEY }),
  });
  const regenerate = useMutation({
    mutationFn: () =>
      withReauth(() =>
        api<{ backup_codes: string[] }>("/auth/totp/backup-codes", { method: "POST" }),
      ),
    onSuccess: (data) => setCodes(data.backup_codes),
  });

  if (!me.data) return null;
  const user = me.data;
  const canToggle = !user.roles.includes("admin");

  return (
    <section className={styles.page}>
      <h1 className={styles.name}>{user.full_name}</h1>
      <dl className={styles.facts}>
        <dt>{t("profile.login")}</dt>
        <dd className="mono">{user.login}</dd>
        <dt>{t("profile.roles")}</dt>
        <dd>{user.roles.map((role) => t(`roles.${role}`)).join(", ")}</dd>
        <dt>{t("totp.title")}</dt>
        <dd>{user.totp_enabled ? t("totp.enabled") : t("totp.disabled")}</dd>
        {student.data && (
          <>
            <dt>{t("student.groups")}</dt>
            <dd>{student.data.groups.join(", ") || "—"}</dd>
            <dt>{t("student.school")}</dt>
            <dd>
              {student.data.school || "—"}
              {student.data.school_grade && <>, {student.data.school_grade}</>}
            </dd>
            <dt>{t("student.target")}</dt>
            <dd>{student.data.target || "—"}</dd>
            <dt>{t("student.targetScore")}</dt>
            <dd className="mono">{student.data.target_score ?? "—"}</dd>
          </>
        )}
      </dl>

      <h2>{t("profile.security")}</h2>
      {codes ? (
        <BackupCodes codes={codes} onDone={() => setCodes(null)} />
      ) : (
        <div className={styles.actions}>
          <Link to="/account/password">{t("menu.password")}</Link>
          <Link to="/account/sessions">{t("menu.sessions")}</Link>
          {!user.totp_enabled && <Link to="/setup-2fa">{t("totp.enable")}</Link>}
          {user.totp_enabled && (
            <Button onClick={() => regenerate.mutate()} disabled={regenerate.isPending}>
              {t("totp.regenerate")}
            </Button>
          )}
          {user.totp_enabled && canToggle && (
            <Button variant="danger" onClick={() => disable.mutate()} disabled={disable.isPending}>
              {t("totp.disable")}
            </Button>
          )}
        </div>
      )}
      {(disable.error ?? regenerate.error) && (
        <p className={styles.error} role="alert">
          {errorMessage(disable.error ?? regenerate.error)}
        </p>
      )}

      {(user.active_role === "teacher" || user.active_role === "student") && (
        <CalendarSection activeRole={user.active_role} />
      )}

      <ThemeSwitch value={theme} onChange={setTheme} />
      <LanguageSwitch />
    </section>
  );
}
