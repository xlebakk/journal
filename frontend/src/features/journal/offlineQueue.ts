/**
 * The teacher's offline queue (stage 13). It lives only in this tab's memory: the
 * user chose that nothing about the children stays on the device. Closing the tab with
 * unsent changes loses them, so the page warns before unload.
 *
 * * A change that cannot reach the server waits here, in order; the screen shows it at once
 *   (the journal caches are patched).
 * * A newer change of the same thing (the same student's mark) replaces the older one.
 * * Versions for optimistic locking are taken when the request is sent, from the last answer
 *   the server gave for that thing — so two queued changes of one mark do not conflict.
 * * Sending stops at the first network error and goes on when the network is back. A 409 is a
 *   conflict for the teacher to decide; any other refusal is shown with its reason.
 */
import type { QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

import { ApiError } from "@/shared/api/client";

export type Queued = {
  id: string;
  /** Changes with the same key replace each other while unsent. */
  key?: string;
  /** What the teacher sees in the list: «Алиев Ф. · 16.11 · н». */
  label: string;
  run: () => Promise<unknown>;
  /** For a conflict: send ours again over the server's newer value. */
  force?: () => Promise<unknown>;
  /** For a conflict after a lost answer: is the server already at our value? */
  alreadyThere?: () => Promise<boolean>;
  /** Shows the change in the cached journal data before the server has it. */
  patch?: (data: unknown) => unknown;
};

export type Problem = { item: Queued; kind: "conflict" | "refused"; error: unknown };

type Snapshot = { pending: Queued[]; problems: Problem[]; syncing: boolean };

let state: Snapshot = { pending: [], problems: [], syncing: false };
const listeners = new Set<() => void>();
const versions = new Map<string, number>();

function set(next: Partial<Snapshot>) {
  state = { ...state, ...next };
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useQueue(): Snapshot {
  return useSyncExternalStore(subscribe, () => state);
}

export function queueSnapshot(): Snapshot {
  return state;
}

export function isNetworkError(error: unknown): boolean {
  return error instanceof TypeError;
}

/**
 * The version to send: the newest of what the server last answered for this thing and what
 * the screen has (versions only grow; an undo or a refresh can make either one newer).
 */
export function versionOf(key: string, fallback: number | null): number | null {
  const remembered = versions.get(key);
  if (remembered === undefined) return fallback;
  return fallback === null ? remembered : Math.max(remembered, fallback);
}

export function rememberVersion(key: string, version: number) {
  versions.set(key, version);
}

export function patchJournal(queryClient: QueryClient, patch: (data: unknown) => unknown) {
  queryClient.setQueriesData({ queryKey: ["journal"] }, (old: unknown) =>
    old === undefined ? old : patch(old),
  );
}

export function enqueue(item: Queued, queryClient: QueryClient) {
  const pending = item.key ? state.pending.filter((p) => p.key !== item.key) : state.pending;
  set({ pending: [...pending, item] });
  if (item.patch) patchJournal(queryClient, item.patch);
}

/** Takes a waiting change back (a grade removed before it was sent). */
export function dequeue(key: string): boolean {
  const before = state.pending.length;
  set({ pending: state.pending.filter((p) => p.key !== key) });
  return state.pending.length < before;
}

export function isPending(key: string): boolean {
  return state.pending.some((p) => p.key === key);
}

export async function flush(queryClient: QueryClient): Promise<void> {
  // «Offline» from the browser is certain; «online» is only a hope, so errors still count.
  if (state.syncing || state.pending.length === 0 || !navigator.onLine) return;
  set({ syncing: true });
  let sent = false;
  try {
    for (;;) {
      const item = state.pending[0];
      if (!item) break;
      try {
        await item.run();
        sent = true;
        set({ pending: state.pending.filter((p) => p !== item) });
      } catch (error) {
        if (isNetworkError(error)) break;
        const conflict = error instanceof ApiError && error.status === 409;
        if (conflict && item.alreadyThere) {
          try {
            if (await item.alreadyThere()) {
              set({ pending: state.pending.filter((p) => p !== item) });
              continue;
            }
          } catch (check) {
            if (isNetworkError(check)) break;
          }
        }
        set({
          pending: state.pending.filter((p) => p !== item),
          problems: [...state.problems, { item, kind: conflict ? "conflict" : "refused", error }],
        });
      }
    }
  } finally {
    set({ syncing: false });
    if (sent && state.pending.length === 0) {
      await queryClient.invalidateQueries({ queryKey: ["journal"] });
    }
  }
}

/** «Оставить моё» for a conflict, or nothing for a refusal; «убрать» drops it. */
export async function resolve(problem: Problem, keepMine: boolean, queryClient: QueryClient) {
  set({ problems: state.problems.filter((p) => p !== problem) });
  if (keepMine && problem.item.force) {
    try {
      await problem.item.force();
    } catch (error) {
      if (isNetworkError(error)) {
        enqueue({ ...problem.item, run: problem.item.force }, queryClient);
        return;
      }
      set({ problems: [...state.problems, { ...problem, kind: "refused", error }] });
    }
  }
  await queryClient.invalidateQueries({ queryKey: ["journal"] });
}

/** Tests only. */
export function resetQueue() {
  state = { pending: [], problems: [], syncing: false };
  versions.clear();
  for (const listener of listeners) listener();
}
