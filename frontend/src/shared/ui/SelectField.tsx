import { useId, type ComponentProps } from "react";

import styles from "./TextField.module.css";

type SelectFieldProps = ComponentProps<"select"> & {
  label: string;
  options: { value: string; label: string }[];
  error?: string;
};

/** Native select: accessible everywhere, styled as a line in an exercise book. */
export function SelectField({ label, options, error, id, className, ...rest }: SelectFieldProps) {
  const autoId = useId();
  const selectId = id ?? autoId;
  return (
    <div className={[styles.field, className].filter(Boolean).join(" ")}>
      <label className={styles.label} htmlFor={selectId}>
        {label}
      </label>
      <select
        id={selectId}
        className={styles.select}
        aria-invalid={error ? true : undefined}
        {...rest}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && <p className={styles.error}>{error}</p>}
    </div>
  );
}
