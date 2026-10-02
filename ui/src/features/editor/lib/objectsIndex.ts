// The game's objects on the map: teleports, gathering spots and the rest, out of sets such as
// assets/object-sets/altgard.json. Coordinates in the sets are percentages of the map size; here
// they are turned into pixels and put into a grid index, so that the nearest point under the
// cursor is found instantly.

import type { ObjectSet } from "@/shared/backend/contract";
import { isResourceIcon } from "@/shared/ui/resourceMarks";

import { iconColor, iconFor, type ObjectIconName } from "./objectIcons";

const CELL = 96; // the side of an index cell, in map pixels

/** The colour of a category that has none of its own — Python sets it while parsing the set. */
const NEUTRAL_COLOR = "#8f99ad";

/**
 * Categories the editor leaves out, by their id in the set: villages, occupation points and
 * battlefields are places, not stops on a route, and the owner found them only clutter. They are
 * not listed, not drawn and not snapped to; the sets themselves keep them.
 */
const LEFT_OUT = new Set(["villages", "occupation", "battlefields"]);

/** A set's category in index form: the id is unique across all of the map's sets. */
export interface IndexCategory {
  id: string;
  file: string;
  name: string;
  parent: string | null;
  color: string;
  /** A mark of its own in place of the dot, where the game has one. */
  icon: ObjectIconName | null;
  count: number;
}

/** An object's point, in map pixels. */
export interface IndexPoint {
  x: number;
  y: number;
  title: string;
  description: string;
  /** id of the category the point belongs to. */
  cat: string;
}

/** Which categories to show: category id -> visible or not. */
export type Visibility = Record<string, boolean>;

export interface ObjectsIndex {
  categories: IndexCategory[];
  byId: Map<string, IndexCategory>;
  points: IndexPoint[];
  nearest: (x: number, y: number, radius: number, visible?: Visibility | null) => IndexPoint | null;
  empty: boolean;
}

/**
 * @param sets  the array of sets from backend.getObjects
 * @param size  [width, height] of the map in pixels
 */
export function buildIndex(
  sets: readonly ObjectSet[] | null | undefined,
  size: readonly [number, number],
): ObjectsIndex {
  const [w, h] = size;
  const categories: IndexCategory[] = [];
  const byId = new Map<string, IndexCategory>();
  const points: IndexPoint[] = [];

  for (const set of sets || []) {
    for (const c of set.categories) {
      if (LEFT_OUT.has(c.id)) continue;
      const id = `${set.file}::${c.id}`;
      const icon = iconFor(c.id, set.mapName);
      const cat: IndexCategory = {
        id,
        file: set.file,
        name: c.name,
        parent: c.parentId ? `${set.file}::${c.parentId}` : null,
        color: icon ? iconColor(icon) : c.color,
        icon,
        count: 0,
      };
      categories.push(cat);
      byId.set(id, cat);
    }
    for (const n of set.nodes) {
      const cat = byId.get(`${set.file}::${n.c}`);
      if (!cat) continue;
      cat.count += 1;
      points.push({
        x: (n.x / 100) * w,
        y: (n.y / 100) * h,
        title: n.t,
        description: n.d,
        cat: cat.id,
      });
    }
  }

  for (const cat of categories) {
    if (!cat.color || cat.color === NEUTRAL_COLOR) {
      const parent = cat.parent ? byId.get(cat.parent) : null;
      if (parent && parent.color) cat.color = parent.color;
    }
  }

  const grid = new Map<string, number[]>();
  points.forEach((p, i) => {
    const key = `${Math.floor(p.x / CELL)}:${Math.floor(p.y / CELL)}`;
    let cell = grid.get(key);
    if (!cell) grid.set(key, (cell = []));
    cell.push(i);
  });

  /** The nearest visible point to (x, y) in map pixels, no farther away than radius. */
  function nearest(
    x: number,
    y: number,
    radius: number,
    visible?: Visibility | null,
  ): IndexPoint | null {
    const cells = Math.max(1, Math.ceil(radius / CELL));
    const cx = Math.floor(x / CELL);
    const cy = Math.floor(y / CELL);
    let best: IndexPoint | null = null;
    let bestDist = radius;
    for (let dx = -cells; dx <= cells; dx += 1) {
      for (let dy = -cells; dy <= cells; dy += 1) {
        const cell = grid.get(`${cx + dx}:${cy + dy}`);
        if (!cell) continue;
        for (const i of cell) {
          // the cells hold indices into points itself, so the point is always there
          const p = points[i]!;
          if (visible && !visible[p.cat]) continue;
          const d = Math.hypot(p.x - x, p.y - y);
          if (d <= bestDist) {
            bestDist = d;
            best = p;
          }
        }
      }
    }
    return best;
  }

  return { categories, byId, points, nearest, empty: points.length === 0 };
}

/** A root category of the tree: its own points, its descendants' points, and the descendants. */
export interface TreeCategory extends IndexCategory {
  total: number;
  children: (IndexCategory & { total: number })[];
}

export function categoryTree(index: ObjectsIndex): TreeCategory[] {
  const roots: IndexCategory[] = [];
  const childrenOf = new Map<string, IndexCategory[]>();
  for (const cat of index.categories) {
    if (cat.parent && index.byId.has(cat.parent)) {
      const list = childrenOf.get(cat.parent) || [];
      list.push(cat);
      childrenOf.set(cat.parent, list);
    } else {
      roots.push(cat);
    }
  }
  const total = (cat: IndexCategory): number =>
    cat.count + (childrenOf.get(cat.id) || []).reduce((s, c) => s + total(c), 0);
  return roots
    .map((cat) => ({
      ...cat,
      total: total(cat),
      children: (childrenOf.get(cat.id) || []).map((c) => ({ ...c, total: c.count })),
    }))
    .filter((cat) => cat.total > 0);
}

/**
 * What to show when a map is opened for the first time: every category that has points, but the
 * gathering resources. The large ones used to start hidden, lest the map be all dots; the owner
 * wants the whole map in view, and a category is one click away from being hidden. The resources
 * are the exception: thousands of them would bury the rest, and a route is rarely drawn by them.
 */
export function defaultVisibility(index: ObjectsIndex): Visibility {
  const visible: Visibility = {};
  for (const cat of index.categories) {
    visible[cat.id] = cat.count > 0 && !(cat.icon && isResourceIcon(cat.icon));
  }
  return visible;
}

/** A point as the text of a step: "Teleports" or "Villages — SafeHaven". */
export function objectLabel(point: { title?: string; description?: string }): string {
  const title = (point.title || "").trim();
  const description = (point.description || "").trim();
  if (title && description) return `${title} — ${description}`;
  return title || description;
}
