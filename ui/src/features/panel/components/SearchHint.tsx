import { useEffect, useState } from "react";

import { useBackendSignal } from "@/shared/backend/BackendProvider";
import type { Stats } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";

/**
 * How long the search has to go on before the hint comes up. A map that is on screen is found
 * within the first detections; a hint that came and went on every Start, or every time the
 * in-game map was closed for a moment, would only push the panel below it up and down.
 */
export const SEARCH_HINT_DELAY_MS = 5000;

export interface SearchHintProps {
  running: boolean;
}

/**
 * The one hint worth giving while the map is not found: exclusive fullscreen cannot be told
 * apart from here, since capture of it is simply black. It sits under the run row rather than
 * in the status header, so Start/Stop never moves when it comes and goes. Subscribes to
 * statsChanged itself, like Status, and re-renders only when "found" flips. The first-run
 * checklist carries the same line.
 */
export default function SearchHint({ running }: SearchHintProps) {
  const t = useT();
  const [found, setFound] = useState(false);
  // The first stats of a run arrive with its first frame. Until then the engine is still
  // building the map's features, which takes seconds on a large map and is not a search.
  const [ticking, setTicking] = useState(false);
  const [waited, setWaited] = useState(false);
  useBackendSignal<Stats | null>(
    "statsChanged",
    (stats) => {
      if (stats) setTicking(true);
      setFound(Boolean(stats?.found));
    },
    { parse: true },
  );
  // On Stop, and again on Start, so a late tick of the last run does not count for this one.
  useEffect(() => {
    setFound(false);
    setTicking(false);
  }, [running]);

  const searching = running && ticking && !found;
  useEffect(() => {
    if (!searching) return undefined;
    const timer = window.setTimeout(() => setWaited(true), SEARCH_HINT_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
      setWaited(false);
    };
  }, [searching]);

  if (!searching || !waited) return null;
  return <p className="pn-search-hint">{t("panel.status.fullscreenHint")}</p>;
}
