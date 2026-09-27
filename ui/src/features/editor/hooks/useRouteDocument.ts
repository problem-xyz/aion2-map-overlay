/**
 * The route document in the editor: name, map, style, markers, and which of those are unsaved.
 *
 * Everything that changes the document lives here and depends on nothing but the stable
 * functions of `useHistory` and `useApi`. That is why the actions object in `EditorContext.ts`
 * can be memoized once: dragging a marker re-renders whoever reads the state, and nobody else.
 */

import { useCallback, useMemo, useRef, useState } from "react";

import type { EditorRequest, MapInfo, MarkerIcon, RouteStyle } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { useLatest } from "@/shared/hooks/useLatest";
import { useT } from "@/shared/i18n";

import type { Point } from "../lib/geometry";
import {
  DEFAULT_ROUTE_STYLE,
  fromRouteDoc,
  makeMarker,
  movedMarker,
  toRouteDoc,
  type EditorMarker,
  markerWithIcon,
  nextMarkerId,
} from "../lib/routeDoc";

import useHistory from "./useHistory";

/**
 * A snapshot of the saved document -- by reference, not by JSON.
 *
 * `useHistory` never copies the arrays, so undoing an edit hands back exactly the array that
 * was saved, and a reference comparison alone clears "dirty". The previous version ran
 * `JSON.stringify` on every frame of a drag.
 */
interface Saved {
  markers: EditorMarker[];
  name: string;
  mapId: string;
  style: RouteStyle;
}

export function useRouteDocument(maps: MapInfo[]) {
  const api = useApi();
  const confirm = useConfirm();
  const t = useT();

  const [routeId, setRouteId] = useState<string | null>(null);
  // Only the first render names the route: after that the name is the user's, and switching
  // language must not overwrite what they typed
  const [name, setNameState] = useState(() => t("editor.defaultName"));
  const [mapId, setMapId] = useState("");
  const [storedSize, setStoredSize] = useState<[number, number]>([0, 0]);
  const [style, setStyle] = useState<RouteStyle>(() => ({ ...DEFAULT_ROUTE_STYLE }));
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);

  const history = useHistory<EditorMarker>([]);
  // Destructured one by one rather than kept as an object: the functions themselves are stable,
  // only the wrapper around them is rebuilt on every change
  const { items: markers, set, setTransient, begin, end, undo, redo, reset } = history;

  const mapMeta = useMemo(() => maps.find((m) => m.id === mapId) || null, [maps, mapId]);
  const size: [number, number] = mapMeta ? mapMeta.size : storedSize;

  const dirty =
    saved !== null &&
    (markers !== saved.markers ||
      name !== saved.name ||
      mapId !== saved.mapId ||
      style !== saved.style);

  // The actions read the document from here and not from the closure: otherwise every edit would
  // produce new callbacks, and memoizing the actions context would mean nothing.
  const docRef = useLatest({ routeId, name, mapId, size, style, markers, dirty });
  const seenSeq = useRef(0);
  const saving = useRef(false);

  const applyRequest = useCallback(
    (req: EditorRequest | null) => {
      if (!req || !req.doc || req.seq <= seenSeq.current) return;
      const doc = req.doc;
      const load = () => {
        seenSeq.current = req.seq;
        const draft = fromRouteDoc(doc);
        setRouteId(req.id || null);
        setNameState(draft.name);
        setMapId(draft.mapId);
        setStoredSize(draft.size);
        setStyle(draft.style);
        reset(draft.markers);
        setSelectedId(null);
        // Exactly the references that went into the state: until something replaces them, the
        // document is not dirty
        setSaved({
          markers: draft.markers,
          name: draft.name,
          mapId: draft.mapId,
          style: draft.style,
        });
      };
      // "The same route" only when an id is there and matches. A new route has no id, and
      // neither does an open one that was never saved: comparing null with null silently wiped
      // the work the second time "New route" was pressed.
      const sameRoute = req.id != null && req.id === docRef.current.routeId;
      if (!docRef.current.dirty || sameRoute) {
        load();
        return;
      }
      void confirm(t("editor.confirm.openOther"), {
        confirmLabel: t("editor.confirm.openOtherAction"),
        danger: true,
      }).then((ok) => {
        // A newer request may have been loaded while the question was up
        if (ok && req.seq > seenSeq.current) load();
      });
    },
    [confirm, docRef, reset, t],
  );

  const save = useCallback(async (): Promise<string | null> => {
    // One write at a time: the Save button only goes dim once the answer is back, and Ctrl+S on
    // key repeat managed to fire several saveRoute calls in a row and breed duplicate files
    if (!api || saving.current) return null;
    saving.current = true;
    // The snapshot is taken before the await: the user can keep editing while the write runs
    const sent = docRef.current;
    const seqAtSave = seenSeq.current;
    try {
      // toRouteDoc is pure and has no `t` of its own: the name an unnamed route is saved under
      // is translated here and handed in
      const res = await api.saveRoute(sent.routeId, toRouteDoc(sent, t("editor.unnamedRoute")));
      if (!res.ok || !res.id) return null;
      // Another route may have arrived in the window during the round-trip: this is no longer
      // our document, and neither the id nor the saved baseline belongs to it
      if (seenSeq.current !== seqAtSave) return res.id;
      setRouteId(res.id);
      setSaved({
        markers: sent.markers,
        name: sent.name,
        mapId: sent.mapId,
        style: sent.style,
      });
      return res.id;
    } finally {
      saving.current = false;
    }
  }, [api, docRef, t]);

  /** Save if needed, then pass the id on: export and copy both work off the saved file. */
  const saveThen = useCallback(
    async (action: (routeId: string) => void) => {
      const { dirty: unsaved, routeId: current } = docRef.current;
      const id = unsaved || !current ? await save() : current;
      if (id) action(id);
    },
    [docRef, save],
  );

  const setName = useCallback((next: string) => setNameState(next), []);

  const changeMap = useCallback(
    (nextId: string) => {
      if (nextId === docRef.current.mapId) return;
      const apply = () => {
        setMapId(nextId);
        // reset, not set: the history belonged to the previous map. Through set, an undo brought
        // fifty markers of map A back over map B -- and that could then be saved.
        reset([]);
        setSelectedId(null);
      };
      if (docRef.current.markers.length === 0) {
        apply();
        return;
      }
      void confirm(t("editor.confirm.changeMap"), {
        confirmLabel: t("editor.confirm.changeMapAction"),
        danger: true,
      }).then((ok) => {
        if (ok) apply();
      });
    },
    [confirm, docRef, reset, t],
  );

  const addMarker = useCallback(
    (point: Point, text?: string, color?: string | null) => {
      const m = makeMarker(point, text, color);
      set((list) => [...list, m]);
      setSelectedId(m.id);
    },
    [set],
  );

  const insertMarker = useCallback(
    (index: number, point: Point, text?: string, color?: string | null) => {
      const m = makeMarker(point, text, color);
      set((list) => {
        const next = list.slice();
        next.splice(index + 1, 0, m);
        return next;
      });
      setSelectedId(m.id);
    },
    [set],
  );

  /**
   * The route comes back to a point: the same one again at the end of the route, label, colour
   * and icon included -- a teleport taken twice. On the map it is a Shift+click on the point,
   * since a plain click there lands on the point and selects it.
   */
  const repeatMarker = useCallback(
    (id: number) => {
      const source = docRef.current.markers.find((m) => m.id === id);
      if (!source) return;
      const m = { ...source, id: nextMarkerId() };
      set((list) => [...list, m]);
      setSelectedId(m.id);
    },
    [docRef, set],
  );

  const moveMarker = useCallback(
    (id: number, point: Point) => {
      setTransient((list) => list.map((m) => (m.id === id ? movedMarker(m, point) : m)));
    },
    [setTransient],
  );

  const deleteMarker = useCallback(
    (id: number) => {
      const list = docRef.current.markers;
      const at = list.findIndex((m) => m.id === id);
      if (at < 0) return;
      set((current) => current.filter((m) => m.id !== id));
      // Deleting the selected point leaves the inspector on the one that takes its number, else
      // on the one before it, so a run of deletions goes on without picking each point again.
      // The selection is held by id, so any other selection needs no shifting.
      const neighbour = list[at + 1] ?? list[at - 1];
      setSelectedId((current) => (current === id ? (neighbour?.id ?? null) : current));
    },
    [docRef, set],
  );

  /** Every point at once, after a question; one history step, so Ctrl+Z brings them all back. */
  const clearMarkers = useCallback(() => {
    if (docRef.current.markers.length === 0) return;
    void confirm(t("editor.confirm.clearPoints"), {
      confirmLabel: t("editor.confirm.clearPointsAction"),
      danger: true,
    }).then((ok) => {
      if (!ok) return;
      set([]);
      setSelectedId(null);
    });
  }, [confirm, docRef, set, t]);

  /**
   * Move a point to another place in the order: a drag in the list, the inspector's arrows,
   * Alt+Up/Down. One history step, so Ctrl+Z puts it back; the position on the map is kept.
   */
  const moveMarkerTo = useCallback(
    (id: number, index: number) => {
      set((list) => {
        const from = list.findIndex((m) => m.id === id);
        const to = Math.max(0, Math.min(list.length - 1, index));
        const marker = list[from];
        if (from < 0 || !marker || from === to) return list;
        const next = list.slice();
        next.splice(from, 1);
        next.splice(to, 0, marker);
        return next;
      });
    },
    [set],
  );

  const setText = useCallback(
    (id: number, text: string) => {
      setTransient((list) => list.map((m) => (m.id === id ? { ...m, text } : m)));
    },
    [setTransient],
  );

  /** A colour change is a finished action, so it is recorded in history: Ctrl+Z undoes it. */
  const setColor = useCallback(
    (id: number, color: string | null) => {
      set((list) => {
        const i = list.findIndex((m) => m.id === id);
        const marker = i < 0 ? undefined : list[i];
        // The same array means `useHistory` records no step: pressing 9 on a marker that has no
        // colour of its own must not leave an empty undo in the history
        if (!marker || (marker.color ?? null) === color) return list;
        const { color: previous, icon, ...rest } = marker;
        const next = list.slice();
        // color and icon are re-appended in that order, last: the key order of a marker is the
        // route file format
        next[i] = { ...rest, ...(color ? { color } : {}), ...(icon ? { icon } : {}) };
        return next;
      });
    },
    [set],
  );

  /**
   * A quest icon beside the point's number, or none, with the colour it brings: one step in the
   * history for both, so one undo takes the icon and its colour back together.
   */
  const setIcon = useCallback(
    (id: number, icon: MarkerIcon | null) => {
      set((list) => {
        const i = list.findIndex((m) => m.id === id);
        const marker = i < 0 ? undefined : list[i];
        if (!marker || (marker.icon ?? null) === icon) return list;
        const next = list.slice();
        next[i] = markerWithIcon(marker, icon);
        return next;
      });
    },
    [set],
  );

  const endEdit = useCallback(
    (id?: number, point?: Point) => {
      if (id !== undefined && point) {
        setTransient((list) => list.map((m) => (m.id === id ? movedMarker(m, point) : m)));
      }
      end();
    },
    [end, setTransient],
  );

  const actions = useMemo(
    () => ({
      setName,
      changeMap,
      select: setSelectedId,
      addMarker,
      insertMarker,
      repeatMarker,
      moveMarker,
      deleteMarker,
      clearMarkers,
      moveMarkerTo,
      setText,
      setColor,
      setIcon,
      beginEdit: begin,
      endEdit,
      undo,
      redo,
      save,
      saveThen,
    }),
    [
      setName,
      changeMap,
      addMarker,
      insertMarker,
      repeatMarker,
      moveMarker,
      deleteMarker,
      clearMarkers,
      moveMarkerTo,
      setText,
      setColor,
      setIcon,
      begin,
      endEdit,
      undo,
      redo,
      save,
      saveThen,
    ],
  );

  return {
    api,
    routeId,
    name,
    mapId,
    mapMeta,
    size,
    style,
    markers,
    selectedId,
    dirty,
    canUndo: history.canUndo,
    canRedo: history.canRedo,
    applyRequest,
    actions,
  };
}
