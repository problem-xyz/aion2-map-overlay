import { useCallback, useState } from "react";

function remembered<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const stored = window.localStorage.getItem(key) ?? "";
    return allowed.find((x) => x === stored) ?? fallback;
  } catch {
    return fallback;
  }
}

/** A view choice kept in the page's own storage: which tab, which filter, between openings. */
export function useRemembered<T extends string>(key: string, allowed: readonly T[], fallback: T) {
  const [value, setValue] = useState<T>(() => remembered(key, allowed, fallback));
  const set = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next);
      } catch {
        /* private mode: the choice lasts until the panel closes */
      }
    },
    [key],
  );
  return [value, set] as const;
}
