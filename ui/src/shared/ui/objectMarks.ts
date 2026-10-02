/**
 * What a route point sits on, told by the mark the game draws for it. The editor snaps a point
 * onto an object; its list of points and the panel's show that object's icon beside the number,
 * a feather beside a point on an Empyrean Trace. Shared, since the panel cannot reach into the
 * editor for it.
 */

import type { ObjectSet } from "@/shared/backend/contract";

import type { ObjectIconName } from "./markIcons";
import { resourceIcon, resourceOf } from "./resourceMarks";

/** The maps of the Elyos, whose teleports the game marks with its blue winged figure. */
const ELYOS_MAPS = new Set(["verteron"]);

/** How near an object a point is on it: within a map pixel, where a snapped point lands. */
export const ON_OBJECT = 1;

/**
 * The icon for a category, by its id in the object set. The Empyrean Trace's and the hidden
 * cube's ids carry the map's name (`empyrean-trace-altgard`); the others are the same on every map.
 * A gathering resource, `gathering-odyle`, has a mark of its own, named as the category.
 */
export function iconFor(categoryId: string, mapName = ""): ObjectIconName | null {
  if (categoryId.startsWith("empyrean-trace")) return "trace";
  if (categoryId === "teleports") {
    return ELYOS_MAPS.has(mapName.toLowerCase()) ? "teleportElyos" : "teleport";
  }
  if (categoryId === "seals") return "seal";
  if (categoryId.startsWith("hidden-cube")) return "cube";
  const resource = resourceOf(categoryId);
  return resource ? resourceIcon(resource) : null;
}

/**
 * The icon of the object under each point, in the points' order: null where a point is on
 * nothing, or on an object the game draws as a plain dot. Points are in map pixels, the sets'
 * nodes in percent of `size`. A map has a few thousand objects and the list is worked out again
 * with every point passed, so they are filed by the whole pixel they fall in, as icons_under in
 * store/objects.py does: a point is measured against its own pixel and the eight around it.
 */
export function iconsUnder(
  sets: readonly ObjectSet[],
  size: readonly [number, number],
  points: readonly { x: number; y: number }[],
): (ObjectIconName | null)[] {
  const [w, h] = size;
  const grid = new Map<string, { x: number; y: number; icon: ObjectIconName | null }[]>();
  for (const set of sets) {
    const icons = new Map(set.categories.map((c) => [c.id, iconFor(c.id, set.mapName)]));
    for (const n of set.nodes) {
      const x = (n.x / 100) * w;
      const y = (n.y / 100) * h;
      const key = `${Math.floor(x)}:${Math.floor(y)}`;
      let cell = grid.get(key);
      if (!cell) grid.set(key, (cell = []));
      cell.push({ x, y, icon: icons.get(n.c) ?? null });
    }
  }
  return points.map((p) => {
    let best = ON_OBJECT;
    let icon: ObjectIconName | null = null;
    const cx = Math.floor(p.x);
    const cy = Math.floor(p.y);
    for (let gx = cx - 1; gx <= cx + 1; gx += 1) {
      for (let gy = cy - 1; gy <= cy + 1; gy += 1) {
        for (const m of grid.get(`${gx}:${gy}`) ?? []) {
          const d = Math.hypot(m.x - p.x, m.y - p.y);
          if (d <= best) {
            best = d;
            icon = m.icon;
          }
        }
      }
    }
    return icon;
  });
}
