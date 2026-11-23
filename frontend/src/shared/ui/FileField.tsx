import { useId, useState, type ComponentProps } from "react";

import { t } from "@/shared/i18n";

import styles from "./TextField.module.css";

type FileFieldProps = Omit<ComponentProps<"input">, "type"> & {
  label: string;
  hint?: string;
  error?: string;
};

/**
 * A file picker with the same caption and note as a text field. The browser's own button
 * speaks the system's language («Выберите файл» in an English interface), so the native input
 * is hidden visually and our button and file name speak the interface's language (stage 19).
 */
export function FileField({
  label,
  hint,
  error,
  id,
  className,
  onChange,
  ...rest
}: FileFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const captionId = `${inputId}-caption`;
  const noteId = `${inputId}-note`;
  const note = error ?? hint;
  const [name, setName] = useState("");
  return (
    <div className={[styles.field, className].filter(Boolean).join(" ")}>
      <span id={captionId} className={styles.label}>
        {label}
      </span>
      <div className={styles.picker}>
        <input
          id={inputId}
          type="file"
          className={styles.fileInput}
          aria-labelledby={captionId}
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          onChange={(event) => {
            setName(event.target.files?.[0]?.name ?? "");
            onChange?.(event);
          }}
          {...rest}
        />
        <label htmlFor={inputId} className={styles.fileButton}>
          {t("common.chooseFile")}
        </label>
        <span className={styles.fileName}>{name || t("common.noFile")}</span>
      </div>
      {note && (
        <p id={noteId} className={error ? styles.error : styles.hint}>
          {note}
        </p>
      )}
    </div>
  );
}
