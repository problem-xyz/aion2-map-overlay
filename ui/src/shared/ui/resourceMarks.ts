/**
 * The gathering resources and their marks, out of assets/marks/resources.json -- the file the
 * overlay draws them by too (store/resources.py), so a resource looks the same over the game as
 * in the lists. Each is a shape on the 24px grid and the colours it is painted in: a layer names
 * a colour by its role ("main", "ink") or gives one outright.
 *
 * In an object set a resource is the category `gathering-<id>`, and its mark is named the same.
 */

import catalog from "../../../../assets/marks/resources.json";

import type { IconLayer } from "./markIcons";

export type ResourceIconName = `gathering-${string}`;

interface ShapeLayer {
  d: string;
  fill?: string;
  stroke?: string;
  width?: number;
}

interface Resource {
  id: string;
  shape: string;
  colors: Partial<Record<string, string>>;
}

const SHAPES: Record<string, readonly ShapeLayer[]> = catalog.shapes;
const RESOURCES: readonly Resource[] = catalog.resources;
const BY_ID = new Map(RESOURCES.map((r) => [r.id, r]));

const PREFIX = "gathering-";

/**
 * How many resources are drawn at once: more, and the map is all marks. The overlay draws no
 * more than this many either (MAX_PICKED in store/resources.py).
 */
export const MAX_PICKED = 3;

/** Every resource, in the order the lists show them. */
export const RESOURCE_IDS: readonly string[] = RESOURCES.map((r) => r.id);

/** The resource a set's category is, or null for any other category. */
export function resourceOf(categoryId: string): string | null {
  if (!categoryId.startsWith(PREFIX)) return null;
  return categoryId.slice(PREFIX.length) || null;
}

/** The mark of a resource, by its id. */
export function resourceIcon(id: string): ResourceIconName {
  return `${PREFIX}${id}`;
}

export function isResourceIcon(name: string): name is ResourceIconName {
  return resourceOf(name) !== null;
}

const layers = new Map<string, readonly IconLayer[]>();

/** A resource mark's layers with its colours filled in; none for a resource not drawn. */
export function resourceLayers(name: ResourceIconName): readonly IconLayer[] {
  const known = layers.get(name);
  if (known) return known;
  const res = BY_ID.get(resourceOf(name) ?? "");
  const shape = res ? SHAPES[res.shape] : undefined;
  if (!res || !shape) return [];
  const paint = (role: string | undefined) => (role ? (res.colors[role] ?? role) : undefined);
  const out = shape.map((l) => ({
    d: l.d,
    fill: paint(l.fill),
    stroke: paint(l.stroke),
    width: l.width,
  }));
  layers.set(name, out);
  return out;
}

/** The colour a resource is known by: its mark's main one. */
export function resourceColor(name: ResourceIconName): string | null {
  return BY_ID.get(resourceOf(name) ?? "")?.colors.main ?? null;
}
