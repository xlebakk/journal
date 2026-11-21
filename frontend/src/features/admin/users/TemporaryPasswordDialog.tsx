import { t } from "@/shared/i18n";
import { Button, Dialog, DialogActions } from "@/shared/ui";

import styles from "./Users.module.css";

type Props = {
  credentials: { login: string; password: string } | null;
  onClose: () => void;
};

/** The temporary password is shown exactly once (SPEC §4); afterwards only a reset helps. */
export function TemporaryPasswordDialog({ credentials, onClose }: Props) {
  return (
    <Dialog
      open={credentials !== null}
      onOpenChange={(open) => !open && onClose()}
      title={t("tempPassword.title")}
      description={t("tempPassword.note")}
    >
      {credentials && (
        <dl className={styles.credential}>
          <dt>{t("tempPassword.login")}</dt>
          <dd>{credentials.login}</dd>
          <dt>{t("tempPassword.password")}</dt>
          <dd>{credentials.password}</dd>
        </dl>
      )}
      <DialogActions>
        <Button variant="primary" onClick={onClose}>
          {t("tempPassword.done")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
