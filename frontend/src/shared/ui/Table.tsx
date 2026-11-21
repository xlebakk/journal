import type { TableHTMLAttributes } from "react";

import styles from "./Table.module.css";

/** Ruled table: thin rules instead of cards. */
export function Table({ className, ...rest }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={[styles.table, className].filter(Boolean).join(" ")} {...rest} />;
}
