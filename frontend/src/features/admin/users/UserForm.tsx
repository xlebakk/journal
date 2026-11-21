import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import { ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Checkbox, SelectField, TextField } from "@/shared/ui";

import type { UserDetail, UserWrite } from "./api";
import { defaults, ROLES, schema, toPayload, type UserFormValues } from "./userPayload";
import styles from "./Users.module.css";

type UserFormProps = {
  user?: UserDetail;
  submitLabel: string;
  onSubmit: (payload: UserWrite) => Promise<unknown>;
};

export function UserForm({ user, submitLabel, onSubmit }: UserFormProps) {
  const form = useForm<UserFormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaults(user),
  });
  const { errors, isSubmitting } = form.formState;
  const roles = useWatch({ control: form.control, name: "roles" });

  useEffect(() => form.reset(defaults(user)), [user, form]);

  const submit = form.handleSubmit(async (values) => {
    try {
      await onSubmit(toPayload(values));
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length) {
        for (const name of ["last_name", "first_name", "middle_name", "login", "roles"] as const) {
          const message = fieldError(error, name);
          if (message) form.setError(name, { message });
        }
      } else if (!(error instanceof Error && error.message === "reauth_cancelled")) {
        form.setError("root", { message: errorMessage(error) });
      }
    }
  });

  const gradeOptions = [
    { value: "", label: "—" },
    ...["9", "10", "11"].map((g) => ({ value: g, label: g })),
  ];

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <div className={styles.grid}>
        <TextField
          label={t("userForm.lastName")}
          error={errors.last_name?.message}
          {...form.register("last_name")}
        />
        <TextField
          label={t("userForm.firstName")}
          error={errors.first_name?.message}
          {...form.register("first_name")}
        />
        <TextField label={t("userForm.middleName")} {...form.register("middle_name")} />
        <TextField
          label={t("userForm.login")}
          hint={user ? undefined : t("userForm.loginHint")}
          autoCapitalize="off"
          spellCheck={false}
          className="mono"
          error={errors.login?.message}
          {...form.register("login")}
        />
      </div>

      <fieldset className={styles.fieldset}>
        <legend>{t("userForm.roles")}</legend>
        <div className={styles.roles}>
          {ROLES.map((role) => (
            <Checkbox
              key={role}
              label={t(`roles.${role}`)}
              value={role}
              {...form.register("roles")}
            />
          ))}
        </div>
        {errors.roles?.message && (
          <p className={styles.error} role="alert">
            {errors.roles.message}
          </p>
        )}
      </fieldset>

      {roles.includes("student") && (
        <fieldset className={styles.fieldset}>
          <legend>{t("userForm.studentSection")}</legend>
          <div className={styles.grid}>
            <TextField label={t("userForm.school")} {...form.register("student.school")} />
            <SelectField
              label={t("userForm.schoolGrade")}
              options={gradeOptions}
              {...form.register("student.school_grade")}
            />
            <TextField label={t("userForm.target")} {...form.register("student.target")} />
            <TextField
              label={t("userForm.targetScore")}
              inputMode="numeric"
              {...form.register("student.target_score")}
            />
            <TextField label={t("userForm.phone")} type="tel" {...form.register("student.phone")} />
          </div>
          <p className={styles.note}>{t("userForm.adminOnly")}</p>
          <div className={styles.grid}>
            <TextField label={t("userForm.parentName")} {...form.register("student.parent_name")} />
            <TextField
              label={t("userForm.parentPhone")}
              type="tel"
              {...form.register("student.parent_phone")}
            />
            <TextField label={t("userForm.adminNote")} {...form.register("student.admin_note")} />
          </div>
        </fieldset>
      )}

      {roles.includes("teacher") && (
        <fieldset className={styles.fieldset}>
          <legend>{t("userForm.teacherSection")}</legend>
          <div className={styles.grid}>
            <TextField label={t("userForm.phone")} type="tel" {...form.register("teacher.phone")} />
          </div>
        </fieldset>
      )}

      {errors.root?.message && (
        <p className={styles.error} role="alert">
          {errors.root.message}
        </p>
      )}
      <div className={styles.actions}>
        <Button type="submit" variant="primary" disabled={isSubmitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
