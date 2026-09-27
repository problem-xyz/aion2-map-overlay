import "leaflet/dist/leaflet.css";
import "./editor.css";

import L, { type Map as LeafletMap } from "leaflet";
import { useCallback, useEffect, useMemo, useRef } from "react";

import { useBackendSignal, useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, MapInfo, NotifyPayload } from "@/shared/backend/contract";
import { useAsk } from "@/shared/hooks/useAsk";
import { useDocumentTitle } from "@/shared/hooks/useDocumentTitle";
import { useLatest } from "@/shared/hooks/useLatest";
import { useT } from "@/shared/i18n";
import { useToasts } from "@/shared/ui/ToastProvider";
import Toasts from "@/shared/ui/Toasts";

import EditorEmpty from "./components/EditorEmpty";
import Inspector from "./components/Inspector";
import LeftDock from "./components/LeftDock";
import MapCanvas from "./components/MapCanvas";
import ShortcutsHint from "./components/ShortcutsHint";
import Toolbar from "./components/Toolbar";
import ZoomControls from "./components/ZoomControls";
import { EditorActionsContext, EditorStateContext } from "./EditorContext";
import type { EditorActions, EditorState, EditorView } from "./EditorContext";
import { useEditorHotkeys } from "./hooks/useEditorHotkeys";
import { useMapObjects } from "./hooks/useMapObjects";
import { useRouteDocument } from "./hooks/useRouteDocument";
import { coveredEdges } from "./lib/coveredEdges";
import { mapBounds, toLatLng } from "./lib/crs";
import { SNAP_PX, type Point } from "./lib/geometry";
import { ZOOM_STEP } from "./lib/smoothZoom";

// Selectors have to return a stable reference: a fresh literal on every call would make
// useSyncExternalStore believe the state had changed, and it would spin forever
const NO_MAPS: MapInfo[] = [];
const NO_TILES: string[] = [];

/**
 * Hands back the previous value while the next one has the same content.
 *
 * `stateChanged` carries the whole state, so every push from Python -- a panel toggle, a saved
 * route -- arrived as new `maps` and `tilesBusy` arrays even when nothing in them had changed,
 * and a new array re-rendered the entire editor: the list, the objects panel, the map scene.
 * The pushes are rare and the two slices are small, so comparing them by JSON costs next to
 * nothing and returns the same reference the editor already rendered.
 */
function byContent<T>(): (next: T) => T {
  let last: T | undefined;
  let lastJson = "";
  return (next) => {
    if (next === last) return next;
    const json = JSON.stringify(next);
    if (last !== undefined && json === lastJson) return last;
    last = next;
    lastJson = json;
    return next;
  };
}

const sameMaps = byContent<MapInfo[]>();
const sameTilesBusy = byContent<string[]>();

const selectReady = (s: AppState | null) => s !== null;
const selectMaps = (s: AppState | null) => (s ? sameMaps(s.maps) : NO_MAPS);
const selectTilesBusy = (s: AppState | null) => (s ? sameTilesBusy(s.tilesBusy) : NO_TILES);
// One primitive each, so a settings push that changed something else re-renders nothing here
const selectViewMode = (s: AppState | null) => s?.settings.editor_route_view ?? "dim";
const selectViewAhead = (s: AppState | null) => s?.settings.editor_route_ahead ?? 3;
const selectViewOpacity = (s: AppState | null) => s?.settings.editor_opacity ?? 1;

interface Live {
  markers: EditorState["markers"];
  mapMeta: MapInfo | null;
  dirty: boolean;
  style: EditorState["style"];
  objects: EditorState["objects"];
  visibleCats: EditorState["visibleCats"];
}

/**
 * A point placed on an object wears its category's colour, and so does the leg leading to it: a
 * feather's point is white, a teleport's purple. The route's own colour is stored as no colour,
 * so the point goes on following the route's.
 */
function inherited(live: Live, color?: string | null): string | null {
  return color && color !== live.style.color ? color : null;
}

/**
 * Does almost nothing itself: it collects the document (`useRouteDocument`), the map objects
 * (`useMapObjects`) and the keys (`useEditorHotkeys`) into two contexts and hands them down.
 * What stays here is whatever needs the Leaflet map itself: snapping onto an object, and
 * panning the map to the selected marker.
 */
export default function EditorPage() {
  const ask = useAsk();
  const t = useT();
  const { push } = useToasts();
  const ready = useBackendState(selectReady);
  const maps = useBackendState(selectMaps);
  const tilesBusyIds = useBackendState(selectTilesBusy);
  const viewMode = useBackendState(selectViewMode);
  const viewAhead = useBackendState(selectViewAhead);
  const viewOpacity = useBackendState(selectViewOpacity);
  const view = useMemo<EditorView>(
    () => ({ mode: viewMode, ahead: viewAhead, opacity: viewOpacity }),
    [viewMode, viewAhead, viewOpacity],
  );

  const doc = useRouteDocument(maps);
  const api = doc.api;
  const mapObjects = useMapObjects(api, doc.mapMeta);
  const mapRef = useRef<LeafletMap | null>(null);

  // Everything the stable handlers read is held in one ref, so that the handlers themselves are
  // not rebuilt on every edit and the actions context stays unchanged
  const live = useLatest<Live>({
    markers: doc.markers,
    mapMeta: doc.mapMeta,
    dirty: doc.dirty,
    style: doc.style,
    objects: mapObjects.objects,
    visibleCats: mapObjects.visibleCats,
  });

  const setMap = useCallback((map: LeafletMap | null) => {
    mapRef.current = map;
  }, []);

  // Through the glide, so quick presses add up instead of each waiting out the last one's animation
  const zoomIn = useCallback(() => mapRef.current?.smoothZoom?.zoomBy(ZOOM_STEP), []);
  const zoomOut = useCallback(() => mapRef.current?.smoothZoom?.zoomBy(-ZOOM_STEP), []);
  const fitRoute = useCallback(() => {
    const map = mapRef.current;
    const { markers, mapMeta } = live.current;
    if (!map || !mapMeta) return;
    const bounds =
      markers.length > 1
        ? L.latLngBounds(markers.map((m) => toLatLng(m.x, m.y))).pad(0.15)
        : mapBounds(mapMeta.size);
    const { topLeft, bottomRight } = coveredEdges(map);
    // A glide still under way would go on moving the map for a frame under the fit's animation
    map.smoothZoom?.stop();
    map.fitBounds(bounds, {
      animate: true,
      paddingTopLeft: topLeft,
      paddingBottomRight: bottomRight,
    });
  }, [live]);

  const focusMarker = useCallback(
    (id: number) => {
      doc.actions.select(id);
      // A frame later: selecting opens the inspector, and it has to be on the page before the
      // free part of the map can be measured
      requestAnimationFrame(() => {
        const { markers, mapMeta } = live.current;
        const m = markers.find((x) => x.id === id);
        const map = mapRef.current;
        if (!m || !map || !mapMeta) return;
        // In to the map's own resolution, one of its pixels to a screen pixel, or no further out
        // than the view already is; and centred in the part of the map the panels leave free
        const zoom = Math.max(map.getZoom(), mapMeta.tiles.zMax);
        const { topLeft, bottomRight } = coveredEdges(map);
        const offset = L.point(
          (topLeft[0] - bottomRight[0]) / 2,
          (topLeft[1] - bottomRight[1]) / 2,
        );
        const point = map.project(toLatLng(m.x, m.y), zoom);
        map.smoothZoom?.stop();
        // setView, not flyTo: flyTo moves the map from script every frame, and that load is what
        // QtWebEngine drew half-finished frames under; Leaflet's zoom animation is plain CSS
        map.setView(map.unproject(point.subtract(offset), zoom), zoom, { animate: true });
      });
    },
    [doc.actions, live],
  );

  const addMarker = useCallback(
    (point: Point, text?: string, color?: string | null) =>
      doc.actions.addMarker(point, text, inherited(live.current, color)),
    [doc.actions, live],
  );

  const insertMarker = useCallback(
    (index: number, point: Point, text?: string, color?: string | null) =>
      doc.actions.insertMarker(index, point, text, inherited(live.current, color)),
    [doc.actions, live],
  );

  /** End of a drag: close to an object, the marker snaps exactly onto it. */
  const endEdit = useCallback(
    (id?: number, point?: Point) => {
      let target = point;
      const { objects, visibleCats, mapMeta } = live.current;
      if (point && objects && mapMeta && mapRef.current) {
        const radius = SNAP_PX / 2 ** (mapRef.current.getZoom() - mapMeta.tiles.zMax);
        const near = objects.nearest(point.x, point.y, radius, visibleCats);
        if (near) target = near;
      }
      doc.actions.endEdit(id, target);
    },
    [doc.actions, live],
  );

  // The context actions are declared as `() => void`: a click handler has no use for a promise,
  // and `onClick={async () => ...}` hides an unhandled rejection.
  const exportRoute = useCallback(
    () => void doc.actions.saveThen((id) => api?.exportRoute(id)),
    [api, doc.actions],
  );
  const copyCode = useCallback(
    () => void doc.actions.saveThen((id) => api?.copyRouteCode(id)),
    [api, doc.actions],
  );
  const importFile = useCallback(() => api?.importRouteFile(), [api]);
  const pasteCode = useCallback(() => api?.pasteRouteCode(), [api]);

  // True once the page has taken the close over -- closed, or put the question up. Python stops
  // its fallback timer on that answer, so a question left unanswered no longer times out.
  const asking = useRef(false);
  const { save } = doc.actions;
  const close = useCallback((): boolean => {
    if (!api) return false;
    if (!live.current.dirty) {
      api.closeEditor();
      return true;
    }
    // The window's X pressed again while the question is up: it is already being asked
    if (asking.current) return true;
    asking.current = true;
    void ask(t("editor.confirm.close"), [
      { id: "discard", label: t("editor.confirm.closeAction"), tone: "danger" },
      { id: "save", label: t("editor.confirm.saveAndClose"), tone: "primary" },
    ])
      .then(async (choice) => {
        if (choice === "discard") api.closeEditor();
        // A save that failed has said why in a toast; the editor stays open with the work in it
        if (choice === "save" && (await save())) api.closeEditor();
      })
      .finally(() => {
        asking.current = false;
      });
    return true;
  }, [api, ask, live, save, t]);

  useBackendSignal("editorRequest", doc.applyRequest, { parse: true });
  // There is nobody but the editor window itself to show the engine's messages: an import
  // error, a rescaled route, "route saved" -- all of it arrives here.
  useBackendSignal<NotifyPayload>("notify", push, { parse: true });

  // The first document does not arrive as a signal: the window may already be open when the
  // panel asks for another route, so it is fetched once here.
  const applyRef = useLatest(doc.applyRequest);
  useEffect(() => {
    if (!api) return undefined;
    let alive = true;
    void api.getEditorRoute().then((req) => {
      if (alive) applyRef.current(req);
    });
    return () => {
      alive = false;
    };
  }, [api, applyRef]);

  // Python asks the page before closing the window: only the page knows about unsaved work
  useEffect(() => {
    window.__requestClose = close;
    return () => {
      delete window.__requestClose;
    };
  }, [close]);

  // Two whole keys rather than a title plus a glued-on marker: where the dot sits in the sentence
  // is the translator's decision, not a concatenation here
  useDocumentTitle(t(doc.dirty ? "editor.title.dirty" : "editor.title.clean", { name: doc.name }));

  const actions = useMemo<EditorActions>(
    () => ({
      ...doc.actions,
      focusMarker,
      addMarker,
      insertMarker,
      endEdit,
      exportRoute,
      copyCode,
      importFile,
      pasteCode,
      close,
      setMap,
      zoomIn,
      zoomOut,
      fitRoute,
      toggleCats: mapObjects.toggleCats,
    }),
    [
      doc.actions,
      focusMarker,
      addMarker,
      insertMarker,
      endEdit,
      exportRoute,
      copyCode,
      importFile,
      pasteCode,
      close,
      setMap,
      zoomIn,
      zoomOut,
      fitRoute,
      mapObjects.toggleCats,
    ],
  );

  const { mapMeta } = doc;
  const tilesBusy = !!mapMeta && (!mapMeta.tiles.ready || tilesBusyIds.includes(mapMeta.id));

  const state = useMemo<EditorState>(
    () => ({
      name: doc.name,
      mapId: doc.mapId,
      maps,
      mapMeta,
      size: doc.size,
      tilesBusy,
      style: doc.style,
      markers: doc.markers,
      selectedId: doc.selectedId,
      dirty: doc.dirty,
      canUndo: doc.canUndo,
      canRedo: doc.canRedo,
      objects: mapObjects.objects,
      visibleCats: mapObjects.visibleCats,
      view,
    }),
    [
      doc.name,
      doc.mapId,
      maps,
      mapMeta,
      doc.size,
      tilesBusy,
      doc.style,
      doc.markers,
      doc.selectedId,
      doc.dirty,
      doc.canUndo,
      doc.canRedo,
      mapObjects.objects,
      mapObjects.visibleCats,
      view,
    ],
  );

  useEditorHotkeys(actions, doc.selectedId, doc.markers);

  // BackendGate shows connecting and error; this is the gap before the first state arrives.
  if (!ready || !api) {
    return <EditorEmpty muted>{t("common.connecting")}</EditorEmpty>;
  }

  return (
    <EditorStateContext.Provider value={state}>
      <EditorActionsContext.Provider value={actions}>
        <div className="editor ed-shell">
          <Toolbar />

          <main className="editor-main">
            {!mapMeta ? (
              // Only a route that names a map this version does not have gets here: a new
              // route is born on the first bundled map, and the select never offers nothing.
              <EditorEmpty title={t("editor.empty.pickMap")}>
                <p className="muted">{t("editor.empty.mapHint")}</p>
              </EditorEmpty>
            ) : tilesBusy ? (
              <EditorEmpty title={t("editor.tiles.preparing")} muted>
                <p>{t("editor.tiles.hint")}</p>
                {/* Both maps are cut on the first start; saying which is done shows it moves. */}
                <ul className="ed-tiles-maps" aria-live="polite">
                  {maps.map((m) => (
                    <li key={m.id}>
                      {m.tiles.ready && !tilesBusyIds.includes(m.id)
                        ? t("editor.tiles.mapReady", { label: m.label })
                        : t("editor.tiles.mapPreparing", { label: m.label })}
                    </li>
                  ))}
                </ul>
              </EditorEmpty>
            ) : (
              <>
                <MapCanvas />
                <ShortcutsHint />
                <ZoomControls />
              </>
            )}
            {/* The panels float over the map, so it keeps the whole window behind them */}
            <LeftDock />
            <Inspector />
          </main>

          <Toasts />
        </div>
      </EditorActionsContext.Provider>
    </EditorStateContext.Provider>
  );
}
