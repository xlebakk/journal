import {
  CalendarDays,
  CircleHelp,
  CircleUserRound,
  LockKeyhole,
  LogIn,
  UserRound,
} from "lucide-react";
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
import { NightSky } from "@/shared/ui/NightSky";
import { PasswordField } from "@/shared/ui/PasswordField";
import { TextField } from "@/shared/ui/TextField";

import { homePath, useBranding, useLogin, useMe, useTotpLogin } from "./api";
import styles from "./AuthPage.module.css";

// No zod here: the login page is the first screen and must stay light.
type LoginForm = { login: string; password: string; remember: boolean };
type TotpForm = { code: string };
const required = (value: string) => value.trim() !== "" || t("common.required");

/** The center's name with its last word in the night's accent: «Учебный **центр**». */
function CenterName({ name }: { name: string }) {
  const words = name.trim().split(/\s+/);
  const last = words.pop() ?? "";
  return (
    <h1 className={styles.center}>
      {words.length > 0 && `${words.join(" ")} `}
      <span className={styles.centerAccent}>{last}</span>
    </h1>
  );
}

/** Login and the other auth steps: a quiet night with the logo, the form on a light panel. */
export function AuthColumn({ children }: { children: React.ReactNode }) {
  const branding = useBranding();
  const [date, weekday] = formatJournalHeader(new Date()).split(" · ");
  return (
    <div className={styles.screen}>
      <section className={styles.panel}>
        <NightSky className={styles.sky} />
        <Logo size="lg" tagline tone="night" className={styles.logo} />
        <div className={styles.panelTop}>
          <CenterName name={branding.data?.center_name || t("app.centerName")} />
          <div className={styles.centerRule} />
        </div>
        <p className={styles.panelFoot}>
          <CalendarDays size={18} strokeWidth={1.6} aria-hidden="true" />
          <span>{date}</span>
          <span className={styles.footRule} />
          <span>{weekday}</span>
        </p>
      </section>
      <main className={styles.side}>
        <svg
          className={styles.wave}
          viewBox="0 0 100 1000"
          preserveAspectRatio="none"
          aria-hidden="true"
          focusable="false"
        >
          <path d="M100 0 H70 C20 180 92 360 46 540 C8 700 78 850 36 1000 H100 Z" />
        </svg>
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
    <>
      <p className={styles.or}>{t("login.or")}</p>
      <p className={styles.helpBlock}>
        <CircleHelp className={styles.helpIcon} size={20} strokeWidth={1.8} aria-hidden="true" />
        <span className={styles.helpTitle}>{t("login.helpTitle")}</span>
        <span className={styles.helpText}>
          {t("login.helpText")}
          {contacts ? `: ${contacts}` : "."}
        </span>
      </p>
    </>
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
        icon={<UserRound size={15} strokeWidth={2} aria-hidden="true" />}
        trailing={<CircleUserRound size={18} strokeWidth={1.6} aria-hidden="true" />}
        autoComplete="username"
        autoCapitalize="off"
        spellCheck={false}
        error={form.formState.errors.login?.message}
        {...form.register("login", { validate: required, setValueAs: (v: string) => v.trim() })}
      />
      <PasswordField
        label={t("login.password")}
        icon={<LockKeyhole size={15} strokeWidth={2} aria-hidden="true" />}
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
        <LogIn size={19} strokeWidth={1.8} aria-hidden="true" />
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
