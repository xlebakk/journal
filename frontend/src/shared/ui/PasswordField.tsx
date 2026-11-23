import { Eye, EyeOff } from "lucide-react";
import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode } from "react";

import { t } from "@/shared/i18n";

import styles from "./TextField.module.css";

type PasswordFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  label: string;
  hint?: string;
  error?: string;
  /** A small pictogram before the caption (decorative). */
  icon?: ReactNode;
};

/** Password with a «показать» toggle. */
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField({ label, hint, error, icon, id, className, ...rest }, ref) {
    const autoId = useId();
    const inputId = id ?? autoId;
    const noteId = `${inputId}-note`;
    const [visible, setVisible] = useState(false);
    const note = error ?? hint;
    return (
      <div className={[styles.field, className].filter(Boolean).join(" ")}>
        <label className={styles.label} htmlFor={inputId}>
          {icon && <span className={styles.icon}>{icon}</span>}
          {label}
        </label>
        <div className={styles.withAction}>
          <input
            ref={ref}
            id={inputId}
            type={visible ? "text" : "password"}
            className={styles.input}
            aria-invalid={error ? true : undefined}
            aria-describedby={note ? noteId : undefined}
            autoCapitalize="off"
            spellCheck={false}
            {...rest}
          />
          <button
            type="button"
            className={styles.action}
            aria-pressed={visible}
            aria-controls={inputId}
            onClick={() => setVisible((v) => !v)}
          >
            {visible ? (
              <EyeOff size={16} strokeWidth={1.6} aria-hidden="true" />
            ) : (
              <Eye size={16} strokeWidth={1.6} aria-hidden="true" />
            )}
            {visible ? t("login.hidePassword") : t("login.showPassword")}
          </button>
        </div>
        {note && (
          <p id={noteId} className={error ? styles.error : styles.hint}>
            {note}
          </p>
        )}
      </div>
    );
  },
);
