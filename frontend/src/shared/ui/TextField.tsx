import { useId, type ComponentProps, type ReactNode } from "react";

import styles from "./TextField.module.css";

type TextFieldProps = ComponentProps<"input"> & {
  label: string;
  hint?: string;
  error?: string;
  /** A small pictogram before the caption (decorative). */
  icon?: ReactNode;
  /** A pictogram at the end of the field (decorative). */
  trailing?: ReactNode;
};

/** A line in an exercise book: only a bottom rule, caption above. */
export function TextField({
  label,
  hint,
  error,
  icon,
  trailing,
  id,
  className,
  ...rest
}: TextFieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const noteId = `${inputId}-note`;
  const note = error ?? hint;
  return (
    <div className={[styles.field, className].filter(Boolean).join(" ")}>
      <label className={styles.label} htmlFor={inputId}>
        {icon && <span className={styles.icon}>{icon}</span>}
        {label}
      </label>
      {trailing ? (
        <div className={styles.withAction}>
          <input
            id={inputId}
            className={styles.input}
            aria-invalid={error ? true : undefined}
            aria-describedby={note ? noteId : undefined}
            {...rest}
          />
          <span className={styles.trailing}>{trailing}</span>
        </div>
      ) : (
        <input
          id={inputId}
          className={styles.input}
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          {...rest}
        />
      )}
      {note && (
        <p id={noteId} className={error ? styles.error : styles.hint}>
          {note}
        </p>
      )}
    </div>
  );
}
