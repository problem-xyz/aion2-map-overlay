import { useCallback, useLayoutEffect, useMemo, useRef, useState } from "react";

/** How many steps are kept; past that the oldest drop out, so history cannot grow forever. */
export const HISTORY_LIMIT = 200;

export type Update<T> = T[] | ((prev: T[]) => T[]);

export interface History<T> {
  items: T[];
  canUndo: boolean;
  canRedo: boolean;
  /** A change that is recorded in history. */
  set: (next: Update<T>) => void;
  /** A change that is not recorded: drag frames, typing. */
  setTransient: (next: Update<T>) => void;
  /** Remember the current value, so that `end` records one history entry for the whole edit. */
  begin: () => void;
  end: () => void;
  undo: () => void;
  redo: () => void;
  /** Start over: there is no history, nothing to undo. */
  reset: (value: T[]) => void;
}

function apply<T>(value: Update<T>, prev: T[]): T[] {
  return typeof value === "function" ? value(prev) : value;
}

interface HistoryState<T> {
  past: T[][];
  present: T[];
  future: T[][];
}

export default function useHistory<T>(initial: T[] = []): History<T> {
  const [state, setState] = useState<HistoryState<T>>({
    past: [],
    present: initial,
    future: [],
  });
  const snapshot = useRef<T[] | null>(null);
  // The present value is kept in a ref instead of being read from inside a `setState` updater:
  // an updater has to stay pure, and StrictMode invokes it twice, so a ref mutated inside one was
  // mutated more than once -- the snapshot was cleared before the second invocation, and the whole
  // edit silently never reached history.
  const present = useRef(state.present);
  useLayoutEffect(() => {
    present.current = state.present;
  });

  const set = useCallback((next: Update<T>) => {
    setState((s) => {
      const value = apply(next, s.present);
      if (value === s.present) return s;
      return { past: [...s.past, s.present].slice(-HISTORY_LIMIT), present: value, future: [] };
    });
  }, []);

  const setTransient = useCallback((next: Update<T>) => {
    setState((s) => {
      const value = apply(next, s.present);
      return value === s.present ? s : { ...s, present: value };
    });
  }, []);

  const begin = useCallback(() => {
    snapshot.current = present.current;
  }, []);

  const end = useCallback(() => {
    const before = snapshot.current;
    snapshot.current = null;
    if (before === null) return;
    setState((s) =>
      before === s.present
        ? s
        : {
            past: [...s.past, before].slice(-HISTORY_LIMIT),
            present: s.present,
            future: [],
          },
    );
  }, []);

  const undo = useCallback(() => {
    setState((s) => {
      const previous = s.past[s.past.length - 1];
      if (previous === undefined) return s;
      return {
        past: s.past.slice(0, -1),
        present: previous,
        future: [s.present, ...s.future].slice(0, HISTORY_LIMIT),
      };
    });
  }, []);

  const redo = useCallback(() => {
    setState((s) => {
      const next = s.future[0];
      if (next === undefined) return s;
      return {
        past: [...s.past, s.present].slice(-HISTORY_LIMIT),
        present: next,
        future: s.future.slice(1),
      };
    });
  }, []);

  const reset = useCallback((value: T[]) => {
    snapshot.current = null;
    setState({ past: [], present: value, future: [] });
  }, []);

  return useMemo(
    () => ({
      items: state.present,
      canUndo: state.past.length > 0,
      canRedo: state.future.length > 0,
      set,
      setTransient,
      begin,
      end,
      undo,
      redo,
      reset,
    }),
    [state, set, setTransient, begin, end, undo, redo, reset],
  );
}
