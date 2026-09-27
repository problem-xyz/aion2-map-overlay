/**
 * The route document: what lies in the file, and what the editor works with.
 *
 * There is exactly one difference — a marker's `id`. The editor needs it so that React and the
 * selection hold on to the marker itself rather than to its index in the array, and so that an
 * insertion in the middle does not shift the selection. It does not reach the file: the route
 * format does not change, and a route saved by this version is read by any other one.
 */

import type { Marker, MarkerIcon, RouteDoc, RouteStyle } from "@/shared/backend/contract";

import type { Point } from "./geometry";
import { QUEST_COLOR } from "./palette";

export const ROUTE_FORMAT = "map-overlay-route";
export const ROUTE_VERSION = 1;

/** Amber — the first colour of the palette (`palette.ts`); the width is in screen pixels. */
export const DEFAULT_ROUTE_STYLE: RouteStyle = { color: "#f2b544", width: 3 };

export interface EditorMarker extends Marker {
  id: number;
}

/** A marker that may or may not have an id: one read from a file does not have it yet. */
export type MarkerLike = Marker & { id?: number };

export interface RouteDraft {
  name: string;
  mapId: string;
  size: [number, number];
  markers: EditorMarker[];
  style: RouteStyle;
}

/** The same on the input of `toRouteDoc`: markers may still be without ids, size is read-only. */
export interface RouteDraftInput {
  name: string;
  mapId: string;
  size: readonly [number, number];
  markers: readonly MarkerLike[];
  style: RouteStyle;
}

let lastId = 0;

/** The next marker id. Unique within the tab — that is enough, it does not go into the file. */
export function nextMarkerId(): number {
  lastId += 1;
  return lastId;
}

/** In the file coordinates are rounded to hundredths of a pixel — plenty on an 8192×8192 map. */
function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

/**
 * `color` is put last and only when the marker has its own: without it the marker is painted with
 * the route's colour. `id` does not go into the file — `stripMarkerIds` takes it off.
 */
export function makeMarker(point: Point, text?: string, color?: string | null): EditorMarker {
  const m: EditorMarker = {
    x: round2(point.x),
    y: round2(point.y),
    text: text || "",
    id: nextMarkerId(),
  };
  if (color) m.color = color;
  return m;
}

/**
 * The marker with a quest icon, or without one. An icon brings its colour -- yellow for a main
 * quest, green for a side one -- and taking the icon off leaves the colour as it is. `color` and
 * `icon` go last, in that order: the key order of a marker is the route file format.
 */
export function markerWithIcon(marker: EditorMarker, icon: MarkerIcon | null): EditorMarker {
  const { color, icon: previous, ...rest } = marker;
  if (!icon) return color ? { ...rest, color } : rest;
  return { ...rest, color: QUEST_COLOR[icon], icon };
}

/** The same marker in a new place. Rounding lives here too, so drag and save cannot diverge. */
export function movedMarker(marker: EditorMarker, point: Point): EditorMarker {
  return { ...marker, x: round2(point.x), y: round2(point.y) };
}

/**
 * How many earlier points of the route stand on the very same spot as each one: a teleport the
 * route comes back to twice has its points 0 and 1 there. Points put on an object take its exact
 * position, so equal coordinates are what "the same object" is.
 */
export function stackOrder(markers: readonly Marker[]): number[] {
  const seen = new Map<string, number>();
  return markers.map((m) => {
    const key = `${m.x},${m.y}`;
    const n = seen.get(key) ?? 0;
    seen.set(key, n + 1);
    return n;
  });
}

/** Hand out ids to markers that came from a file or from a share code. An own id is kept. */
export function withMarkerIds(markers: readonly MarkerLike[]): EditorMarker[] {
  return markers.map((m) => {
    if (m.id === undefined) return { ...m, id: nextMarkerId() };
    // a foreign id moves the counter too: otherwise the next new marker would get the same
    // number, and two markers would go into React under one key
    lastId = Math.max(lastId, m.id);
    return { ...m, id: m.id };
  });
}

/**
 * Strip the ids before writing. The order of the remaining keys is left alone — that order is the
 * file format.
 */
export function stripMarkerIds(markers: readonly MarkerLike[]): Marker[] {
  return markers.map(({ id, ...marker }) => marker);
}

/**
 * `fallbackName` is what an unnamed route is called in the file. It is passed in rather than kept
 * here as a constant: the name a user reads has to be translated, and this module is pure -- the
 * caller holds `t` (`editor.unnamedRoute`).
 */
export function toRouteDoc(draft: RouteDraftInput, fallbackName: string): RouteDoc {
  return {
    format: ROUTE_FORMAT,
    version: ROUTE_VERSION,
    name: draft.name.trim() || fallbackName,
    map: draft.mapId || "",
    mapSize: [draft.size[0], draft.size[1]],
    markers: stripMarkerIds(draft.markers),
    style: draft.style,
  };
}

/** Older routes may have been saved without a style. */
export function fromRouteDoc(doc: RouteDoc): RouteDraft {
  return {
    name: doc.name,
    mapId: doc.map,
    size: [doc.mapSize[0], doc.mapSize[1]],
    markers: withMarkerIds(doc.markers ?? []),
    // a copy, not DEFAULT_ROUTE_STYLE itself: the editor keeps the style in state and edits it in
    // place, and the shared constant would then be inherited by every route after this one
    style: doc.style || { ...DEFAULT_ROUTE_STYLE },
  };
}
