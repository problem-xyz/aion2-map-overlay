import { useEffect, useMemo, useState } from "react";

import type { ObjectSet, ProgressState } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { type MarkIconName, questIcon } from "@/shared/ui/markIcons";
import { iconsUnder } from "@/shared/ui/objectMarks";

/**
 * Each point's icon, as the editor's list of points shows it: its own quest star, else the icon
 * of the object it sits on -- in the order of `progress.markers`, null where there is neither.
 *
 * The map's objects are asked for once per map, not per render: the progress changes with every
 * point passed, the objects never.
 */
export function usePointIcons(
  mapId: string | undefined,
  progress: ProgressState,
): (MarkIconName | null)[] {
  const api = useApi();
  const [objects, setObjects] = useState<{ map: string; sets: ObjectSet[] } | null>(null);

  useEffect(() => {
    if (!api || !mapId) return undefined;
    let live = true;
    void api.getObjects(mapId).then((sets) => {
      if (live) setObjects({ map: mapId, sets });
    });
    return () => {
      live = false;
    };
  }, [api, mapId]);

  const { markers, map } = progress;
  const sets = objects && objects.map === mapId ? objects.sets : null;
  return useMemo(() => {
    const placed = markers.map((m) => ({ x: m.x ?? Number.NaN, y: m.y ?? Number.NaN }));
    const under = sets && map ? iconsUnder(sets, [map[0], map[1]], placed) : [];
    return markers.map((m, i) => (m.icon ? questIcon(m.icon) : (under[i] ?? null)));
  }, [markers, map, sets]);
}
