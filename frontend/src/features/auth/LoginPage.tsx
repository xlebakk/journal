import { useState } from "react";
import { useForm } from "react-hook-form";
import { Navigate, useNavigate } from "react-router";

import { ApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { isNativeApp } from "@/platform";
import { t } from "@/shared/i18n";
import { formatJournalHeader } from "@/shared/lib/time";
import { shouldShowIosInstallHint } from "@/shared/lib/userAgent";
// Direct imports, not the @/shared/ui barrel: the first screen must not pull every component.
import { Button } from "@/shared/ui/Button";
import { Checkbox } from "@/shared/ui/Checkbox";
import { LanguageSwitch } from "@/shared/ui/LanguageSwitch";
import { Logo } from "@/shared/ui/Logo";
import { PasswordField } from "@/shared/ui/PasswordField";
import { TextField } from "@/shared/ui/TextField";

import { homePath, useBranding, useLogin, useMe, useTotpLogin } from "./api";
import styles from "./AuthPage.module.css";

// No zod here: the login page is the first screen and must stay light (SPEC §15).
type LoginForm = { login: string; password: string; remember: boolean };
type TotpForm = { code: string };
const required = (value: string) => value.trim() !== "" || t("common.required");

/** Login and the other auth steps: a quiet ruled panel with the center, the form on white. */
export function AuthColumn({ children }: { children: React.ReactNode }) {
  const branding = useBranding();
  const contacts = branding.data?.contacts;
  return (
    <div className={styles.screen}>
      <section className={styles.panel}>
        <Logo size="lg" tagline className={styles.logo} />
        <div className={styles.panelTop}>
          <h1 className={styles.center}>{branding.data?.center_name || t("app.centerName")}</h1>
          <p className={styles.year}>{t("login.forWhom")}</p>
        </div>
        <div className={styles.panelFoot}>
          <p className={styles.date}>{formatJournalHeader(new Date())}</p>
          {contacts && <p className={styles.contacts}>{contacts}</p>}
        </div>
      </section>
      <main className={styles.side}>
        <LanguageSwitch className={styles.language} />
        <div className={styles.form}>{children}</div>
      </main>
    </div>
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
    <form className={styles.fields} onSubmit={submit} noValidate>
      <h2 className={styles.title}>{t("login.signIn")}</h2>
      <TextField
        label={t("login.login")}
        autoComplete="username"
        autoCapitalize="off"
        spellCheck={false}
        error={form.formState.errors.login?.message}
        {...form.register("login", { validate: required, setValueAs: (v: string) => v.trim() })}
      />
      <PasswordField
        label={t("login.password")}
        autoComplete="current-password"
        error={form.formState.errors.password?.message}
        {...form.register("password", { validate: required })}
      />
      {/* The app always stays signed in for 30 days (refresh token); the choice is web-only. */}
      {!isNativeApp && <Checkbox label={t("login.remember")} {...form.register("remember")} />}
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
  const form = useForm<TotpForm>({ defaultValues: { code: "" } });

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
    <form className={styles.fields} onSubmit={submit} noValidate>
      <h2 className={styles.title}>{t("login.totpTitle")}</h2>
      <p className={styles.note}>{t("login.totpHint")}</p>
      <TextField
        label={t("login.totpCode")}
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={9}
        className="mono"
        error={form.formState.errors.code?.message}
        {...form.register("code", {
          validate: (v: string) => v.trim().length >= 6 || t("common.required"),
          setValueAs: (v: string) => v.trim(),
        })}
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
      {!isNativeApp && shouldShowIosInstallHint() && (
        <p className={styles.help}>{t("install.ios")}</p>
      )}
    </AuthColumn>
  );
}
