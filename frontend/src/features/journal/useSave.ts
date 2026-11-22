import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { useInvalidateJournal } from "./api";
import {
  enqueue,
  flush,
  isNetworkError,
  patchJournal,
  queueSnapshot,
  type Queued,
} from "./offlineQueue";

export type Action = {
  run: () => Promise<unknown>;
  /** Built from the result of `run`; offered for 10 seconds (SPEC §7.2). */
  undo?: (result: unknown) => (() => Promise<unknown>) | undefined;
  /** Stage 13: how the change waits without network; without it the change needs the network. */
  offline?: Omit<Queued, "id" | "run">;
  /** A change made only here (a queued grade taken back): applied to the cache after `run`. */
  localPatch?: (data: unknown) => unknown;
};

export type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: Date }
  | { kind: "undone" }
  | { kind: "queued" }
  | { kind: "error"; error: unknown; action: Action };

const UNDO_MS = 10_000;

/** Every journal write: save status in words, retry on failure, undo for ten seconds. */
export function useSave() {
  const invalidate = useInvalidateJournal();
  const queryClient = useQueryClient();
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const [undo, setUndo] = useState<(() => Promise<unknown>) | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const queue = useCallback(
    (action: Action & { offline: NonNullable<Action["offline"]> }) => {
      enqueue({ id: crypto.randomUUID(), run: action.run, ...action.offline }, queryClient);
      setUndo(null);
      setState({ kind: "queued" });
      void flush(queryClient);
      return true;
    },
    [queryClient],
  );

  const perform = useCallback(
    async (action: Action): Promise<boolean> => {
      // Without network, or behind changes still waiting: keep the order, wait in the queue.
      if (action.offline && (!navigator.onLine || queueSnapshot().pending.length > 0)) {
        return queue({ ...action, offline: action.offline });
      }
      setState({ kind: "saving" });
      try {
        const result = await action.run();
        if (action.localPatch) patchJournal(queryClient, action.localPatch);
        await invalidate();
        setState({ kind: "saved", at: new Date() });
        const inverse = action.undo?.(result);
        if (timer.current) clearTimeout(timer.current);
        setUndo(inverse ? () => inverse : null);
        if (inverse) timer.current = setTimeout(() => setUndo(null), UNDO_MS);
        return true;
      } catch (error) {
        if (action.offline && isNetworkError(error)) {
          return queue({ ...action, offline: action.offline });
        }
        setState({ kind: "error", error, action });
        if (!isNetworkError(error)) await invalidate();
        return false;
      }
    },
    [invalidate, queryClient, queue],
  );

  const runUndo = useCallback(async () => {
    if (!undo) return;
    setUndo(null);
    const action: Action = { run: undo };
    try {
      await undo();
      await invalidate();
      setState({ kind: "undone" });
    } catch (error) {
      setState({ kind: "error", error, action });
    }
  }, [undo, invalidate]);

  const retry = state.kind === "error" ? () => void perform(state.action) : null;
  return {
    state,
    perform,
    retry,
    undo: undo ? () => void runUndo() : null,
    busy: state.kind === "saving",
  };
}
