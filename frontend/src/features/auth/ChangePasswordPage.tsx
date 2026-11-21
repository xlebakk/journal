import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { useNavigate } from "react-router";
import { z } from "zod";

import { errorMessage, fieldError } from "@/shared/api/errors";
import { ApiError } from "@/shared/api/client";
import { t } from "@/shared/i18n";
import { Button, PasswordField, StrengthMeter } from "@/shared/ui";

import { useChangePassword, useMe } from "./api";
import styles from "./AuthPage.module.css";
import { AuthColumn } from "./LoginPage";

const schema = z
  .object({
    current_password: z.string().min(1, t("common.required")),
    new_password: z.string().min(10, t("password.tooShort")),
    repeat: z.string(),
  })
  .refine((v) => v.new_password === v.repeat, {
    path: ["repeat"],
    message: t("password.mismatch"),
  });
type Form = z.infer<typeof schema>;

/** Forced after a temporary password (full screen) or voluntary from the menu. */
export function ChangePasswordForm({ onDone }: { onDone: () => void }) {
  const me = useMe();
  const change = useChangePassword();
  const form = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { current_password: "", new_password: "", repeat: "" },
  });
  const newPassword = useWatch({ control: form.control, name: "new_password" });
  const personal = me.data ? [me.data.login, me.data.last_name, me.data.first_name] : [];

  const submit = form.handleSubmit(async ({ current_password, new_password }) => {
    try {
      await change.mutateAsync({ current_password, new_password });
      form.reset();
      onDone();
    } catch {
      // Shown below.
    }
  });

  const serverError = change.error instanceof ApiError && change.error.code ? change.error : null;
  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <PasswordField
        label={t("password.current")}
        autoComplete="current-password"
        error={
          form.formState.errors.current_password?.message ??
          fieldError(change.error, "current_password")
        }
        {...form.register("current_password")}
      />
      <div>
        <PasswordField
          label={t("password.new")}
          autoComplete="new-password"
          hint={t("password.hint")}
          error={
            form.formState.errors.new_password?.message ?? fieldError(change.error, "new_password")
          }
          {...form.register("new_password")}
        />
        <StrengthMeter password={newPassword} personal={personal} />
      </div>
      <PasswordField
        label={t("password.repeat")}
        autoComplete="new-password"
        error={form.formState.errors.repeat?.message}
        {...form.register("repeat")}
      />
      {serverError && (
        <p className={styles.error} role="alert">
          {errorMessage(serverError)}
        </p>
      )}
      <Button type="submit" variant="primary" disabled={change.isPending}>
        {t("password.submit")}
      </Button>
    </form>
  );
}

export function ForcedPasswordChangePage() {
  const navigate = useNavigate();
  return (
    <AuthColumn>
      <h2>{t("password.title")}</h2>
      <p className={styles.note}>{t("password.forcedNote")}</p>
      <ChangePasswordForm onDone={() => navigate("/", { replace: true })} />
    </AuthColumn>
  );
}

export function PasswordPage() {
  const [done, setDone] = useState(false);
  return (
    <section className={styles.form}>
      <h1>{t("password.title")}</h1>
      {done && (
        <p className={styles.success} role="status">
          {t("password.done")}
        </p>
      )}
      <div className={styles.column}>
        <ChangePasswordForm onDone={() => setDone(true)} />
      </div>
    </section>
  );
}
