import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";

import { ApiError } from "@/shared/api/client";
import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { useMe } from "@/features/auth/api";
import { Button, Checkbox, PasswordField, SelectField, TextField } from "@/shared/ui";

import type { UserDetail, UserWrite } from "./api";
import { defaults, ROLES, schema, SECTIONS, toPayload, type UserFormValues } from "./userPayload";
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
  const superadminFlag = useWatch({ control: form.control, name: "is_superadmin" });
  const me = useMe().data;
  // Administrators are created and given rights only by the super administrator (stage 16).
  const superadmin = Boolean(me?.is_superadmin);
  const roleChoices = ROLES.filter(
    (role) => role !== "admin" || superadmin || roles.includes(role),
  );

  useEffect(() => form.reset(defaults(user)), [user, form]);

  const submit = form.handleSubmit(async (values) => {
    if (!user && values.password.length < 10) {
      form.setError("password", { message: t("password.tooShort") });
      return;
    }
    try {
      await onSubmit(toPayload(values, superadmin));
    } catch (error) {
      if (error instanceof ApiError && Object.keys(error.fields).length) {
        for (const name of [
          "last_name",
          "first_name",
          "middle_name",
          "login",
          "roles",
          "password",
        ] as const) {
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

      {!user && (
        <div className={styles.grid}>
          <PasswordField
            label={t("userForm.password")}
            hint={t("password.hint")}
            autoComplete="new-password"
            error={errors.password?.message}
            {...form.register("password")}
          />
          <Checkbox label={t("userForm.mustChange")} {...form.register("must_change_password")} />
        </div>
      )}

      <fieldset className={styles.fieldset}>
        <legend>{t("userForm.roles")}</legend>
        <div className={styles.roles}>
          {roleChoices.map((role) => (
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

      {roles.includes("admin") && superadmin && (
        <fieldset className={styles.fieldset}>
          <legend>{t("userForm.adminRights")}</legend>
          <TextField
            label={t("userForm.position")}
            hint={t("userForm.positionHint")}
            maxLength={80}
            {...form.register("position")}
          />
          <Checkbox label={t("userForm.superadmin")} {...form.register("is_superadmin")} />
          {!superadminFlag && (
            <>
              <p className={styles.note}>{t("userForm.sectionsHint")}</p>
              <div className={styles.roles}>
                {SECTIONS.map((section) => (
                  <Checkbox
                    key={section}
                    label={t(`sections.${section}`)}
                    value={section}
                    {...form.register("admin_sections")}
                  />
                ))}
              </div>
            </>
          )}
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
