/**
 * Two contexts instead of thirty-five props.
 *
 * State and actions are split on purpose. The state changes on every frame of a marker drag,
 * the actions never change: a component that only needs the handlers -- the sidebar buttons,
 * the list of object sets -- does not re-render together with the marker under the cursor.
 */

import type { Map as LeafletMap } from "leaflet";
import { createContext, useContext } from "react";

import type { EditorRouteView, MapInfo, MarkerIcon, RouteStyle } from "@/shared/backend/contract";

import type { Point } from "./lib/geometry";
import type { ObjectsIndex, Visibility } from "./lib/objectsIndex";
import type { EditorMarker } from "./lib/routeDoc";

/** How the route is drawn in the editor: the editor_* settings, the route view panel's. */
export interface EditorView {
  mode: EditorRouteView;
  ahead: number;
  opacity: number;
}

export interface EditorState {
  name: string;
  mapId: string;
  maps: MapInfo[];
  /** The selected entry of `maps`, or null when no map is chosen or it has been deleted. */
  mapMeta: MapInfo | null;
  /** Map size in pixels: the selected map's, else the size recorded in the route. */
  size: [number, number];
  /** The map is still being cut into tiles -- it cannot be drawn on yet. */
  tilesBusy: boolean;
  style: RouteStyle;
  markers: EditorMarker[];
  /** The selected marker, by id rather than by index: inserting in the middle must not move it. */
  selectedId: number | null;
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  objects: ObjectsIndex | null;
  visibleCats: Visibility;
  view: EditorView;
}

export interface EditorActions {
  setName: (name: string) => void;
  changeMap: (mapId: string) => void;

  select: (id: number | null) => void;
  /** Select a marker and fly the map in to it: a click in the points list, "Show on map". */
  focusMarker: (id: number) => void;
  addMarker: (point: Point, text?: string, color?: string | null) => void;
  /** Insert after the marker at `index` -- which is what `nearestSegment` returns. */
  insertMarker: (index: number, point: Point, text?: string, color?: string | null) => void;
  /** The route comes back to this point: a copy of it at the end of the route. */
  repeatMarker: (id: number) => void;
  moveMarker: (id: number, point: Point) => void;
  /** Remove a point; when it was the selected one, its neighbour in the route is selected. */
  deleteMarker: (id: number) => void;
  /** Remove every point, after a confirmation, as one undoable step. */
  clearMarkers: () => void;
  /** Put a point at `index` in the order, as one undoable step. */
  moveMarkerTo: (id: number, index: number) => void;
  setText: (id: number, text: string) => void;
  setColor: (id: number, color: string | null) => void;
  /** A quest icon beside the point's number, or none; undoable. */
  setIcon: (id: number, icon: MarkerIcon | null) => void;

  /** Start and end of one edit: a drag or a run of typing becomes a single history entry. */
  beginEdit: () => void;
  endEdit: (id?: number, point?: Point) => void;
  undo: () => void;
  redo: () => void;

  save: () => Promise<string | null>;
  exportRoute: () => void;
  copyCode: () => void;
  importFile: () => void;
  pasteCode: () => void;
  close: () => void;

  /** The canvas hands its Leaflet instance here: the zoom is needed both for snapping and panTo. */
  setMap: (map: LeafletMap | null) => void;
  zoomIn: () => void;
  zoomOut: () => void;
  /** Frame the whole route, or the whole map when the route is empty. */
  fitRoute: () => void;

  toggleCats: (ids: string[], value: boolean) => void;
}

export const EditorStateContext = createContext<EditorState | null>(null);
export const EditorActionsContext = createContext<EditorActions | null>(null);

export function useEditorState(): EditorState {
  const value = useContext(EditorStateContext);
  if (!value) throw new Error("useEditorState must be used inside the editor");
  return value;
}

export function useEditorActions(): EditorActions {
  const value = useContext(EditorActionsContext);
  if (!value) throw new Error("useEditorActions must be used inside the editor");
  return value;
}
