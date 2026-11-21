import { t, type MessageKey } from "@/shared/i18n";

import styles from "./StrengthMeter.module.css";
import { passwordStrength } from "./strength";

/** Simple 4-step strength scale (SPEC §4). The server's validators have the final word. */
export function StrengthMeter({ password, personal }: { password: string; personal: string[] }) {
  const score = passwordStrength(password, personal);
  const label = t(`password.strength${score}` as MessageKey);
  return (
    <div className={styles.meter}>
      <span className={styles.segments} aria-hidden="true">
        {[1, 2, 3, 4].map((step) => (
          <span key={step} className={step <= score ? styles[`on${score}`] : styles.off} />
        ))}
      </span>
      <span className={styles.label}>
        {t("password.strength")}: {password ? label : "—"}
      </span>
    </div>
  );
}
