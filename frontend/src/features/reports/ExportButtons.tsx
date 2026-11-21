import { useState } from "react";

import styles from "@/features/schedule/SchedulePage.module.css";
import { canDownload } from "@/platform";
import { errorMessage } from "@/shared/api/errors";
import { t } from "@/shared/i18n";
import { Button } from "@/shared/ui";

import { useExport, type Query } from "./api";

/** Print, XLSX, CSV for one report. Cancelling the password dialog is not an error. */
export function ExportButtons({
  path,
  query,
  print = true,
}: {
  path: string;
  query: Query;
  print?: boolean;
}) {
  const exportFile = useExport();
  const [error, setError] = useState<unknown>(null);
  const [pending, setPending] = useState(false);
  if (!canDownload) return <p className={styles.note}>{t("common.webOnly")}</p>;
  const run = async (kind: "xlsx" | "csv") => {
    setError(null);
    setPending(true);
    try {
      await exportFile(path, query, kind);
    } catch (e) {
      if (!(e instanceof Error && e.message === "reauth_cancelled")) setError(e);
    } finally {
      setPending(false);
    }
  };
  return (
    <div className={`${styles.row} ${styles.noPrint}`}>
      {print && <Button onClick={() => window.print()}>{t("reports.print")}</Button>}
      <Button onClick={() => void run("xlsx")} disabled={pending}>
        {t("reports.xlsx")}
      </Button>
      <Button onClick={() => void run("csv")} disabled={pending}>
        {t("reports.csv")}
      </Button>
      {error !== null && (
        <span className={styles.error} role="alert">
          {errorMessage(error)}
        </span>
      )}
    </div>
  );
}
