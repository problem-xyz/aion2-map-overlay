import { useEffect } from "react";

import { useLatest } from "./useLatest";

/** Close-on-outside-click for popovers. Listens on pointerdown so it beats a focus change. */
export function useClickOutside<T extends HTMLElement>(
  ref: React.RefObject<T | null>,
  onOutside: () => void,
  active = true,
) {
  const latest = useLatest(onOutside);
  useEffect(() => {
    if (!active) return undefined;
    const handler = (e: PointerEvent) => {
      const node = ref.current;
      if (node && !node.contains(e.target as Node)) latest.current();
    };
    document.addEventListener("pointerdown", handler, true);
    return () => document.removeEventListener("pointerdown", handler, true);
  }, [ref, active, latest]);
}
