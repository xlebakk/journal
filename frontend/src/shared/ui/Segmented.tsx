import styles from "./Segmented.module.css";

type Option<T extends string> = { value: T; label: string };

/**
 * Two or three views of one screen as a pill switch, after the eDonish schedule («Моё
 * расписание | Расписание класса»). Tabs for assistive technology.
 */
export function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Option<T>[];
  onChange: (value: T) => void;
}) {
  return (
    <div className={styles.segmented} role="tablist" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={option.value === value}
          className={styles.segment}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
