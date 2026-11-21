import { useId, type ComponentProps } from "react";

import styles from "./TextField.module.css";

type FileFieldProps = Omit<ComponentProps<"input">, "type"> & {
  label: string;
  hint?: string;
  error?: string;
};

/** A file picker with the same caption and note as a text field. */
export function FileField({ label, hint, error, id, className, ...rest }: FileFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const noteId = `${inputId}-note`;
  const note = error ?? hint;
  return (
    <div className={[styles.field, className].filter(Boolean).join(" ")}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      <input
        id={inputId}
        type="file"
        className={styles.file}
        aria-invalid={error ? true : undefined}
        aria-describedby={note ? noteId : undefined}
        {...rest}
      />
      {note && (
        <p id={noteId} className={error ? styles.error : styles.hint}>
          {note}
        </p>
      )}
    </div>
  );
}
