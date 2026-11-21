import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";

import { fieldError, errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button, RuledSkeleton, TextField } from "@/shared/ui";

import { ME_KEY, useConfirmTotp, useMe, useTotpSetup } from "./api";
import styles from "./AuthPage.module.css";
import { AuthColumn } from "./LoginPage";

function groupSecret(secret: string): string {
  return secret.match(/.{1,4}/g)?.join(" ") ?? secret;
}

export function BackupCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  return (
    <div className={styles.form}>
      <h2>{t("totp.codesTitle")}</h2>
      <p className={styles.note}>{t("totp.codesNote")}</p>
      <ol className={styles.codes}>
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ol>
      <Button variant="primary" onClick={onDone}>
        {t("totp.codesDone")}
      </Button>
    </div>
  );
}

/** QR → code → backup codes. Mandatory for administrators (SPEC §4). */
export function TotpSetupPage() {
  const me = useMe();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setup = useTotpSetup(Boolean(me.data && !me.data.totp_enabled));
  const confirm = useConfirmTotp();
  const [code, setCode] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      await confirm.mutateAsync(code.trim());
    } catch {
      setCode("");
    }
  };

  const finish = async () => {
    await queryClient.invalidateQueries({ queryKey: ME_KEY });
    navigate("/", { replace: true });
  };

  return (
    <AuthColumn>
      <h2>{t("totp.title")}</h2>
      {me.data?.totp_setup_required && <p className={styles.note}>{t("totp.forcedNote")}</p>}
      {confirm.data ? (
        <BackupCodes codes={confirm.data.backup_codes} onDone={finish} />
      ) : setup.isPending ? (
        <RuledSkeleton rows={4} />
      ) : setup.error ? (
        <p className={styles.error}>{errorMessage(setup.error)}</p>
      ) : (
        <form className={styles.form} onSubmit={submit} noValidate>
          <p className={styles.note}>{t("totp.step1")}</p>
          <img className={styles.qr} src={setup.data.qr} alt={t("totp.qrAlt")} />
          <div>
            <p className={styles.note}>{t("totp.manual")}</p>
            <p className={styles.secret}>{groupSecret(setup.data.secret)}</p>
          </div>
          <p className={styles.note}>{t("totp.step2")}</p>
          <TextField
            label={t("login.totpCode")}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            error={fieldError(confirm.error, "code")}
          />
          <Button type="submit" variant="primary" disabled={confirm.isPending || code.length < 6}>
            {t("totp.confirm")}
          </Button>
        </form>
      )}
    </AuthColumn>
  );
}
