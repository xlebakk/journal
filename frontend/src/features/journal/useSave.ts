import { useCallback, useEffect, useRef, useState } from "react";

import { useInvalidateJournal } from "./api";

export type Action = {
  run: () => Promise<unknown>;
  /** Built from the result of `run`; offered for 10 seconds (SPEC §7.2). */
  undo?: (result: unknown) => (() => Promise<unknown>) | undefined;
};

export type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; at: Date }
  | { kind: "undone" }
  | { kind: "error"; error: unknown; action: Action };

const UNDO_MS = 10_000;

/** Every journal write: save status in words, retry on failure, undo for ten seconds. */
export function useSave() {
  const invalidate = useInvalidateJournal();
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const [undo, setUndo] = useState<(() => Promise<unknown>) | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const perform = useCallback(
    async (action: Action): Promise<boolean> => {
      setState({ kind: "saving" });
      try {
        const result = await action.run();
        await invalidate();
        setState({ kind: "saved", at: new Date() });
        const inverse = action.undo?.(result);
        if (timer.current) clearTimeout(timer.current);
        setUndo(inverse ? () => inverse : null);
        if (inverse) timer.current = setTimeout(() => setUndo(null), UNDO_MS);
        return true;
      } catch (error) {
        setState({ kind: "error", error, action });
        await invalidate();
        return false;
      }
    },
    [invalidate],
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
