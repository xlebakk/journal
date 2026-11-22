import { useQuery, type QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { api, setQueryScope, type Schemas } from "@/shared/api/client";

export type Child = Schemas["Child"];

const STORAGE_KEY = "journal.child";
const listeners = new Set<() => void>();

function stored(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

let selected: string | null = stored();
// Before the first request: the student pages then ask for the remembered child.
if (selected) setQueryScope("/student/", { child: selected });

/** The parent's children (stage 14); the server orders them as it picks the default one. */
export function useChildren(enabled: boolean) {
  return useQuery({
    queryKey: ["parent", "children"],
    queryFn: () => api<Child[]>("/parent/children"),
    enabled,
  });
}

export function useSelectedChild(): string | null {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => selected,
  );
}

/** Switch every student page to another child: forget the other child's data at once. */
export function selectChild(id: string | null, queryClient: QueryClient) {
  if (id === selected) return;
  selected = id;
  setQueryScope("/student/", id ? { child: id } : null);
  try {
    if (id) sessionStorage.setItem(STORAGE_KEY, id);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Private mode: the choice lasts until the page reloads.
  }
  for (const listener of listeners) listener();
  void queryClient.resetQueries({
    predicate: (query) => !["me", "parent"].includes(String(query.queryKey[0])),
  });
}

/** Whether the parent has linked children; undefined while loading or for other roles. */
export function useHasChildren(enabled: boolean): boolean | undefined {
  const children = useChildren(enabled);
  return children.data ? children.data.length > 0 : undefined;
}
