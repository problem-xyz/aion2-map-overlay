import { useEffect, useRef } from "react";

/**
 * A ref that always holds the newest value.
 *
 * Used where a long-lived subscription must call the current handler without being torn down
 * and re-established on every render -- reconnecting a Qt signal each time a parent re-renders
 * drops payloads in the gap.
 */
export function useLatest<T>(value: T) {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  });
  return ref;
}
