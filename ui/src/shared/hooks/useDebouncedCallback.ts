import { useCallback, useEffect, useMemo, useRef } from "react";

import { useLatest } from "./useLatest";

export interface DebouncedCallback<A extends unknown[]> {
  (...args: A): void;
  flush: () => void;
  cancel: () => void;
}

/**
 * Call `fn` at most once per `ms`, trailing edge.
 *
 * `flush` exists because a debounced call that never happens is a lost edit: dragging a slider
 * and immediately closing the window must still send the last value. Unmount flushes for the
 * same reason.
 */
export function useDebouncedCallback<A extends unknown[]>(
  fn: (...args: A) => void,
  ms: number,
): DebouncedCallback<A> {
  const latest = useLatest(fn);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pending = useRef<A | null>(null);

  const cancel = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    pending.current = null;
  }, []);

  const flush = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    const args = pending.current;
    pending.current = null;
    if (args) latest.current(...args);
  }, [latest]);

  const debounced = useMemo(() => {
    const run = ((...args: A) => {
      pending.current = args;
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        timer.current = null;
        const queued = pending.current;
        pending.current = null;
        if (queued) latest.current(...queued);
      }, ms);
    }) as DebouncedCallback<A>;
    run.flush = flush;
    run.cancel = cancel;
    return run;
  }, [ms, latest, flush, cancel]);

  useEffect(() => () => flush(), [flush]);

  return debounced;
}
