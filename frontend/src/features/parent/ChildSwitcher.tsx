import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { t } from "@/shared/i18n";
import { SelectField } from "@/shared/ui";

import { selectChild, useChildren, useSelectedChild } from "./children";
import styles from "./Parent.module.css";

/** «Ребёнок: Алиев Фарход» in the parent's header; a select when there are several. */
export function ChildSwitcher() {
  const queryClient = useQueryClient();
  const children = useChildren(true);
  const selected = useSelectedChild();
  const list = children.data ?? [];

  // A remembered child who is no longer linked: back to the first one.
  useEffect(() => {
    if (!children.data) return;
    if (selected && !children.data.some((c) => c.id === selected)) {
      selectChild(children.data[0]?.id ?? null, queryClient);
    }
  }, [children.data, selected, queryClient]);

  if (list.length === 0) return null;
  if (list.length === 1) {
    return <span className={styles.single}>{list[0]!.full_name}</span>;
  }
  return (
    <SelectField
      className={styles.switcher}
      label={t("parent.child")}
      value={selected ?? list[0]!.id}
      onChange={(e) => selectChild(e.target.value, queryClient)}
      options={list.map((c) => ({ value: c.id, label: c.full_name }))}
    />
  );
}
