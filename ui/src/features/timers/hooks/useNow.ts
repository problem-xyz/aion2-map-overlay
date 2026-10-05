import { useEffect, useState } from "react";

/**
 * The clock, read again every `everyMs`, for the countdowns. One interval per caller: the timers
 * page has one, at its root, and hands the moment down.
 */
export function useNow(everyMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(id);
  }, [everyMs]);
  return now;
}
