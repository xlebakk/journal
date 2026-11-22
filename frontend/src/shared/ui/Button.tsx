import type { ButtonHTMLAttributes } from "react";

import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "danger";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant };

/** Primary: one per screen. Labels start lowercase. */
export function Button({
  variant = "secondary",
  className,
  type = "button",
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      className={[styles.button, styles[variant], className].filter(Boolean).join(" ")}
      {...rest}
    />
  );
}
