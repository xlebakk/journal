import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { errorMessage, fieldError } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, Checkbox, Dialog, DialogActions, PasswordField } from "@/shared/ui";

import { usersApi, useInvalidateUsers, type UserDetail } from "./api";
import styles from "./Users.module.css";

/** «Задать новый пароль»: the administrator types it; the user's sessions end (stage 16). */
export function SetPasswordDialog({
  user,
  open,
  onClose,
}: {
  user: UserDetail;
  open: boolean;
  onClose: () => void;
}) {
  const invalidate = useInvalidateUsers();
  const [password, setPassword] = useState("");
  const [mustChange, setMustChange] = useState(false);
  const save = useMutation({
    mutationFn: () => usersApi.setPassword(user.id, { password, must_change_password: mustChange }),
    onSuccess: async () => {
      setPassword("");
      await invalidate();
      onClose();
    },
  });
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && onClose()}
      title={t("userActions.setPasswordTitle")}
      description={t("userActions.setPasswordNote", { login: user.login })}
    >
      <div className={styles.form}>
        <PasswordField
          label={t("userForm.password")}
          hint={t("password.hint")}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldError(save.error, "password")}
        />
        <Checkbox
          label={t("userForm.mustChange")}
          checked={mustChange}
          onChange={(e) => setMustChange(e.target.checked)}
        />
        {save.error && !fieldError(save.error, "password") && (
          <p className={styles.error} role="alert">
            {errorMessage(save.error)}
          </p>
        )}
      </div>
      <DialogActions>
        <Button
          variant="primary"
          disabled={password.length < 10 || save.isPending}
          onClick={() => save.mutate()}
        >
          {t("userActions.setPassword")}
        </Button>
        <Button onClick={onClose}>{t("common.cancel")}</Button>
      </DialogActions>
    </Dialog>
  );
}
