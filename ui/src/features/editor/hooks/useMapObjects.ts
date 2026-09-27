/**
 * The selected map's objects: an index for looking up what is under the cursor, and which
 * categories are shown.
 *
 * Visibility is remembered per map in localStorage: the sets are large, and ticking the boxes
 * again on every open is no fun at all. The key carries the map id, so different maps keep
 * different settings.
 */

import { useCallback, useEffect, useState } from "react";

import type { BackendApi } from "@/shared/backend/api";
import type { MapInfo } from "@/shared/backend/contract";
import { useLatest } from "@/shared/hooks/useLatest";

import {
  buildIndex,
  defaultVisibility,
  type ObjectsIndex,
  type Visibility,
} from "../lib/objectsIndex";

const visibleKey = (mapId: string) => `mo.objects.${mapId}`;

function loadVisible(mapId: string): Visibility | null {
  try {
    // localStorage can hold anything: trust the shape, not the fact that JSON.parse succeeded
    const parsed: unknown = JSON.parse(window.localStorage.getItem(visibleKey(mapId)) || "null");
    return parsed && typeof parsed === "object" ? (parsed as Visibility) : null;
  } catch {
    return null;
  }
}

function save(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* private mode, or writes are forbidden -- we can live without it */
  }
}

export function useMapObjects(api: BackendApi | null, mapMeta: MapInfo | null) {
  const [objects, setObjects] = useState<ObjectsIndex | null>(null);
  const [visibleCats, setVisibleCats] = useState<Visibility>({});

  // Only strings go into the dependencies: `mapMeta` arrives as a new object with every state
  // Python sends, and the effect would re-read the sets ten times a second
  const mapKey = mapMeta ? mapMeta.id : "";
  const setsKey = mapMeta ? mapMeta.objects.map((s) => s.file).join("|") : "";
  const sizeRef = useLatest<[number, number]>(mapMeta ? mapMeta.size : [0, 0]);

  useEffect(() => {
    // Another map's points must not show over the new map, not even for the half-frame the
    // request takes
    setObjects(null);
    if (!api || !mapKey) {
      setVisibleCats({});
      return undefined;
    }
    let alive = true;
    void api.getObjects(mapKey).then((sets) => {
      if (!alive) return;
      const index = buildIndex(sets, sizeRef.current);
      setObjects(index.empty ? null : index);
      const defaults = defaultVisibility(index);
      const stored = loadVisible(mapKey) || {};
      const visible: Visibility = {};
      for (const c of index.categories) {
        visible[c.id] = (c.id in stored ? stored[c.id] : defaults[c.id]) ?? false;
      }
      setVisibleCats(visible);
    });
    return () => {
      alive = false;
    };
  }, [api, mapKey, setsKey, sizeRef]);

  const mapKeyRef = useLatest(mapKey);
  const visibleRef = useLatest(visibleCats);

  const toggleCats = useCallback(
    (ids: string[], value: boolean) => {
      // Computed and written outside the updater: React treats an updater as pure and calls it
      // twice in StrictMode, which would push the state it then discards into localStorage too
      const next = { ...visibleRef.current };
      for (const id of ids) next[id] = value;
      if (mapKeyRef.current) save(visibleKey(mapKeyRef.current), JSON.stringify(next));
      setVisibleCats(next);
    },
    [mapKeyRef, visibleRef],
  );

  return { objects, visibleCats, toggleCats };
}
