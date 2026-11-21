import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";
import { z } from "zod";

import { ApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { formatJournalHeader } from "@/shared/lib/time";
import { Button, Checkbox, PasswordField, TextField } from "@/shared/ui";

import { homePath, useBranding, useLogin, useMe, useTotpLogin } from "./api";
import styles from "./AuthPage.module.css";

const loginSchema = z.object({
  login: z.string().trim().min(1, t("common.required")),
  password: z.string().min(1, t("common.required")),
  remember: z.boolean(),
});
type LoginForm = z.infer<typeof loginSchema>;

const totpSchema = z.object({ code: z.string().trim().min(6, t("common.required")) });
type TotpForm = z.infer<typeof totpSchema>;

export function AuthColumn({ children }: { children: React.ReactNode }) {
  const branding = useBranding();
  return (
    <main className={styles.column}>
      <p className={`mono ${styles.date}`}>{formatJournalHeader(new Date())}</p>
      <h1 className={styles.center}>{branding.data?.center_name || t("app.centerName")}</h1>
      <p className={styles.subtitle}>{t("login.subtitle")}</p>
      {children}
    </main>
  );
}

function HelpLine() {
  const branding = useBranding();
  const contacts = branding.data?.contacts;
  return (
    <p className={styles.help}>
      {t("login.help")}
      {contacts ? `: ${contacts}` : "."}
    </p>
  );
}

function PasswordStep({ onTotp }: { onTotp: () => void }) {
  const login = useLogin();
  const navigate = useNavigate();
  const form = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
    defaultValues: { login: "", password: "", remember: false },
  });

  const submit = form.handleSubmit(async (values) => {
    try {
      const result = await login.mutateAsync(values);
      if (result.step === "totp") onTotp();
      else navigate("/", { replace: true });
    } catch {
      form.resetField("password");
    }
  });

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <TextField
        label={t("login.login")}
        autoComplete="username"
        autoCapitalize="off"
        spellCheck={false}
        error={form.formState.errors.login?.message}
        {...form.register("login")}
      />
      <PasswordField
        label={t("login.password")}
        autoComplete="current-password"
        error={form.formState.errors.password?.message}
        {...form.register("password")}
      />
      <Checkbox label={t("login.remember")} {...form.register("remember")} />
      {login.error && (
        <p className={styles.error} role="alert">
          {errorMessage(login.error)}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={login.isPending}>
        {t("login.submit")}
      </Button>
    </form>
  );
}

function TotpStep({ onBack }: { onBack: () => void }) {
  const totp = useTotpLogin();
  const navigate = useNavigate();
  const form = useForm<TotpForm>({
    resolver: zodResolver(totpSchema),
    defaultValues: { code: "" },
  });

  const submit = form.handleSubmit(async ({ code }) => {
    try {
      await totp.mutateAsync(code);
      navigate("/", { replace: true });
    } catch {
      form.resetField("code");
    }
  });

  const expired = totp.error instanceof ApiError && totp.error.code === "totp_session_expired";
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <h2>{t("login.totpTitle")}</h2>
      <p className={styles.note}>{t("login.totpHint")}</p>
      <TextField
        label={t("login.totpCode")}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={9}
        className="mono"
        error={form.formState.errors.code?.message}
        {...form.register("code")}
      />
      {totp.error && (
        <p className={styles.error} role="alert">
          {errorMessage(totp.error)}
        </p>
      )}
      <div className={styles.row}>
        <Button type="submit" variant="primary" disabled={totp.isPending || expired}>
          {t("login.totpSubmit")}
        </Button>
        <Button onClick={onBack}>{t("login.totpBack")}</Button>
      </div>
    </form>
  );
}

export function LoginPage() {
  const me = useMe();
  const [step, setStep] = useState<"password" | "totp">("password");
  if (me.data) return <Navigate to={homePath(me.data.active_role)} replace />;
  return (
    <AuthColumn>
      {step === "password" ? (
        <PasswordStep onTotp={() => setStep("totp")} />
      ) : (
        <TotpStep onBack={() => setStep("password")} />
      )}
      <HelpLine />
    </AuthColumn>
  );
}
