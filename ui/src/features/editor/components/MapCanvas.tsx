import type {
  Bounds,
  LatLng,
  LatLngBounds,
  LeafletEventHandlerFnMap,
  LeafletMouseEvent,
  Map as LeafletMap,
  Point as LeafletPoint,
} from "leaflet";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { MapContainer, TileLayer, useMap, useMapEvents } from "react-leaflet";

import type { RouteStyle } from "@/shared/backend/contract";
import { useLatest } from "@/shared/hooks/useLatest";
import { cubeSprite, iconSprite, type ObjectIconName } from "@/shared/ui/markIcons";

import { useEditorActions, useEditorState } from "../EditorContext";
import createCanvasOverlay, { type CanvasOverlayLayer } from "../lib/CanvasOverlay";
import { coveredEdges } from "../lib/coveredEdges";
import { mapBounds, pixelCRS, toPoint } from "../lib/crs";
import {
  ARROW_L,
  ARROW_W,
  FAR_OPACITY,
  SNAP_PX,
  arrowPolygon,
  isNearLeg,
  isNearPoint,
  nearestSegment,
  type Point,
} from "../lib/geometry";
import {
  objectLabel,
  type IndexPoint,
  type ObjectsIndex,
  type Visibility,
} from "../lib/objectsIndex";
import { stackOrder, type EditorMarker } from "../lib/routeDoc";
// Importing it also registers the handler with L.Map, before MapContainer builds the map
import { ZOOM_STEP } from "../lib/smoothZoom";

import RouteMarker from "./RouteMarker";

const TAU = Math.PI * 2;
const OBJECT_R = 4.5;
const DARK = "rgba(15, 17, 22, 0.8)";
const MIN_OBJECT_SCALE = 0.02; // far enough out, object dots merge into mush — do not draw them
const SMALL_OBJECT_SCALE = 0.08; // below this scale dots are drawn smaller so they do not clump
const SMALL_OBJECT_R = 3;
// An icon is a dot's mark at a size it can be told apart at: well larger than the dot, and
// smaller again far out, where there are many of them
const OBJECT_ICON = 30;
const SMALL_OBJECT_ICON = 21;
// The arrow beside a cube above or below the ground about it, as the overlay draws it over the
// game: up at the cube's top right corner, down at its bottom right. In parts of the icon's side.
const LEVEL_SIDE = 11 / 24;
const LEVEL_X = 8 / 24;
const LEVEL_FILL = "#f2f4f8";
const CULL_PAD = 20; // margin past the screen edge: a point just outside it is still half visible
const HINT_R = 9; // circle of the "insert a marker here" hint
const HINT_CROSS = 4;

/** What is under the cursor: a map object, or the spot on the line where a new marker would go. */
type Hover =
  { kind: "object"; point: IndexPoint } | { kind: "segment"; point: Point; index: number };

/** Whether the canvas has to be drawn again: moving within one object's snap circle changes nothing. */
function sameHover(a: Hover | null, b: Hover | null): boolean {
  if (a === b) return true;
  if (!a || !b) return false;
  if (a.kind === "object" && b.kind === "object") return a.point === b.point;
  if (a.kind === "segment" && b.kind === "segment") {
    return a.index === b.index && a.point.x === b.point.x && a.point.y === b.point.y;
  }
  return false;
}

interface ColorGroup {
  color: string;
  points: IndexPoint[];
}

interface IconGroup {
  icon: ObjectIconName;
  points: IndexPoint[];
}

/** Draw snapshot: everything `drawScene` reads within one frame. */
interface SceneData {
  map: LeafletMap;
  zMax: number;
  markers: readonly EditorMarker[];
  /** The selected point's index: the route is drawn as the player sees it heading there. */
  focus: number | null;
  /** How many legs from `focus` are drawn in full. */
  ahead: number;
  /** The route line's and arrows' opacity. */
  opacity: number;
  style: RouteStyle;
  groups: readonly ColorGroup[];
  icons: readonly IconGroup[];
  objects: ObjectsIndex | null;
}

/** Whether two routes draw the same line: positions, and the colours its legs take. */
function samePath(a: readonly EditorMarker[], b: readonly EditorMarker[]): boolean {
  if (a === b) return true;
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    const p = a[i];
    const q = b[i];
    if (!p || !q || p.x !== q.x || p.y !== q.y || p.color !== q.color) return false;
  }
  return true;
}

const layerCanvases = { far: null, near: null } as Record<"far" | "near", HTMLCanvasElement | null>;

/**
 * Draw onto `ctx` at `alpha`, through a canvas of its own when that is less than 1: the part
 * of the route is drawn there in full, and laid on the map faded as a whole. Faded leg by leg
 * instead, every outline showed through the colour over it and every crossing came out darker.
 */
function drawFaded(
  ctx: CanvasRenderingContext2D,
  key: "far" | "near",
  alpha: number,
  draw: (c: CanvasRenderingContext2D) => void,
): void {
  if (alpha >= 1) {
    draw(ctx);
    return;
  }
  const canvas = (layerCanvases[key] ??= document.createElement("canvas"));
  const { width, height } = ctx.canvas;
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const layer = canvas.getContext("2d");
  if (!layer) return;
  layer.setTransform(1, 0, 0, 1, 0, 0);
  layer.clearRect(0, 0, width, height);
  layer.setTransform(ctx.getTransform());
  draw(layer);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = alpha;
  ctx.drawImage(canvas, 0, 0);
  ctx.restore();
}

let accent: string | null = null;

/** The colour of the route's end, the accent its marker wears; read from the page once. */
function endColor(): string {
  accent ??=
    getComputedStyle(document.documentElement).getPropertyValue("--color-accent").trim() ||
    "#9acbed";
  return accent;
}

/** Grouping is by color so the canvas can draw all points of one color in a single pass. */
function colorGroups(objects: ObjectsIndex | null, visible: Visibility): ColorGroup[] {
  if (!objects) return [];
  const groups = new Map<string, IndexPoint[]>();
  for (const p of objects.points) {
    if (!visible[p.cat]) continue;
    const cat = objects.byId.get(p.cat);
    // a category with an icon is drawn by iconGroups instead
    if (!cat || cat.icon) continue;
    let list = groups.get(cat.color);
    if (!list) groups.set(cat.color, (list = []));
    list.push(p);
  }
  return [...groups].map(([color, points]) => ({ color, points }));
}

/** The visible points of the categories that have an icon, one group per icon. */
function iconGroups(objects: ObjectsIndex | null, visible: Visibility): IconGroup[] {
  if (!objects) return [];
  const groups = new Map<ObjectIconName, IndexPoint[]>();
  for (const p of objects.points) {
    if (!visible[p.cat]) continue;
    const icon = objects.byId.get(p.cat)?.icon;
    if (!icon) continue;
    let list = groups.get(icon);
    if (!list) groups.set(icon, (list = []));
    list.push(p);
  }
  return [...groups].map(([icon, points]) => ({ icon, points }));
}

function drawScene(
  ctx: CanvasRenderingContext2D,
  bounds: Bounds,
  data: SceneData,
  hover: Hover | null,
): void {
  const { map, zMax, markers, focus, ahead, opacity, style, groups, icons, objects } = data;
  const k = 2 ** (map.getZoom() - zMax);
  const origin = map.getPixelOrigin();
  const sx = (x: number) => x * k - origin.x;
  const sy = (y: number) => y * k - origin.y;
  // L.Bounds types the corners as optional; the bounds drawScene is called with always have them
  const min = bounds.min as LeafletPoint;
  const max = bounds.max as LeafletPoint;
  const visibleAt = (x: number, y: number) =>
    x > min.x - CULL_PAD && x < max.x + CULL_PAD && y > min.y - CULL_PAD && y < max.y + CULL_PAD;

  // game objects go under the route; far out their dots are smaller so they do not clump
  if (k >= MIN_OBJECT_SCALE) {
    const radius = k < SMALL_OBJECT_SCALE ? SMALL_OBJECT_R : OBJECT_R;
    ctx.lineWidth = 1;
    ctx.strokeStyle = DARK;
    for (const group of groups) {
      ctx.fillStyle = group.color;
      ctx.beginPath();
      for (const p of group.points) {
        const x = sx(p.x);
        const y = sy(p.y);
        if (!visibleAt(x, y)) continue;
        ctx.moveTo(x + radius, y);
        ctx.arc(x, y, radius, 0, TAU);
      }
      ctx.fill();
      ctx.stroke();
    }
    // the icons over the dots: one bitmap per icon and size, stamped at every point
    const size = k < SMALL_OBJECT_SCALE ? SMALL_OBJECT_ICON : OBJECT_ICON;
    const ratio = window.devicePixelRatio || 1;
    for (const group of icons) {
      const sprite = iconSprite(group.icon, size, ratio);
      if (!sprite) continue;
      for (const p of group.points) {
        const x = sx(p.x);
        const y = sy(p.y);
        if (!visibleAt(x, y)) continue;
        // a cube in its group's colour, so the spots of one cube read as one
        const own = p.tint !== undefined ? cubeSprite(p.tint, size, ratio) : null;
        ctx.drawImage(own ?? sprite, x - size / 2, y - size / 2, size, size);
      }
    }
    const side = size * LEVEL_SIDE;
    ctx.beginPath();
    for (const group of icons) {
      for (const p of group.points) {
        if (!p.level) continue;
        const x = sx(p.x) + size * LEVEL_X;
        const y = sy(p.y);
        if (!visibleAt(x, y)) continue;
        const top = p.level > 0 ? y - size / 2 : y + size / 2 - side;
        const [tip, base] = p.level > 0 ? [top + 1.5, top + side - 2] : [top + side - 1.5, top + 2];
        ctx.moveTo(x + side / 2, tip);
        ctx.lineTo(x + side - 1, base);
        ctx.lineTo(x + 1, base);
        ctx.closePath();
      }
    }
    ctx.fillStyle = LEVEL_FILL;
    ctx.strokeStyle = DARK;
    ctx.lineWidth = 1.5;
    ctx.lineJoin = "round";
    ctx.fill();
    ctx.stroke();
  }

  const pts = markers.map((m) => ({ x: sx(m.x), y: sy(m.y) }));

  // Route line: each leg in the colour of the point it leads to, as the overlay draws it over the
  // game -- the way to a side quest is green. Legs go down from the end of the route back to its
  // start, each in its own dark outline with its chevron, so where the route crosses itself the
  // leg walked first lies on top and its outline cuts through the later one. Drawn start first,
  // a leg for later in the route hid the one the player is on. With a point selected, only the
  // legs about it are drawn in full, as the overlay draws the ones ahead of the player.
  if (pts.length > 1) {
    const end = endColor();
    const legColor = (i: number) => {
      const to = markers[i + 1];
      if (to?.color) return to.color;
      // the end of the route wears the accent, as its marker does
      return i + 1 === markers.length - 1 ? end : style.color;
    };
    const stroke = (c: CanvasRenderingContext2D, path: readonly Point[], color: string) => {
      for (const [pen, width] of [
        [DARK, style.width + 3],
        [color, style.width],
      ] as const) {
        c.strokeStyle = pen;
        c.lineWidth = width;
        c.beginPath();
        path.forEach((p, n) => (n === 0 ? c.moveTo(p.x, p.y) : c.lineTo(p.x, p.y)));
        c.stroke();
      }
    };
    const drawLegs = (c: CanvasRenderingContext2D, near: boolean) => {
      c.lineCap = "round";
      c.lineJoin = "round";
      for (let i = pts.length - 2; i >= 0; i -= 1) {
        const a = pts[i];
        const b = pts[i + 1];
        if (!a || !b || isNearLeg(i, focus, ahead) !== near) continue;
        stroke(c, [a, b], legColor(i));
        if (!near) continue;
        // one chevron mid-leg, an open V drawn as the line is: the dark outline, then the colour
        const tri = arrowPolygon(a, b, ARROW_L, ARROW_W);
        if (tri) stroke(c, [tri[1], tri[0], tri[2]], legColor(i));
      }
    };
    if (focus !== null) drawFaded(ctx, "far", opacity * FAR_OPACITY, (c) => drawLegs(c, false));
    drawFaded(ctx, "near", opacity, (c) => drawLegs(c, true));
  }

  if (hover && hover.kind === "segment") {
    const x = sx(hover.point.x);
    const y = sy(hover.point.y);
    ctx.fillStyle = "rgba(110, 168, 255, 0.92)";
    ctx.strokeStyle = DARK;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, HINT_R, 0, TAU);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = "#0f1116";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x - HINT_CROSS, y);
    ctx.lineTo(x + HINT_CROSS, y);
    ctx.moveTo(x, y - HINT_CROSS);
    ctx.lineTo(x, y + HINT_CROSS);
    ctx.stroke();
  } else if (hover && hover.kind === "object") {
    const x = sx(hover.point.x);
    const y = sy(hover.point.y);
    // round an icon as round a dot: a little outside what is drawn
    const iconed = objects?.byId.get(hover.point.cat)?.icon;
    const ring = iconed
      ? (k < SMALL_OBJECT_SCALE ? SMALL_OBJECT_ICON : OBJECT_ICON) / 2 + 3
      : OBJECT_R + 4;
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(x, y, ring, 0, TAU);
    ctx.stroke();
  }
}

interface SceneProps {
  bounds: LatLngBounds;
}

function Scene({ bounds }: SceneProps) {
  const { mapMeta, markers, style, selectedId, objects, visibleCats, view } = useEditorState();
  const actions = useEditorActions();
  const map = useMap();
  const zMax = mapMeta ? mapMeta.tiles.zMax : 0;
  const overlayRef = useRef<CanvasOverlayLayer | null>(null);
  const dataRef = useRef<SceneData | null>(null);
  // Hover lives outside React: it changes on every mouse move, and as state it re-rendered the
  // whole scene -- every marker, the tooltip -- for what is a canvas redraw and a moved <div>.
  const hoverRef = useRef<Hover | null>(null);
  const tipRef = useRef<HTMLDivElement | null>(null);
  const fitted = useRef(false);

  // Leaflet remembers the container size from the moment the map is created. In the editor window
  // the layout settles a little later, and the window can be resized, so we watch the size.
  useEffect(() => {
    const refit = () => {
      map.invalidateSize({ animate: false });
      if (!fitted.current) {
        const { topLeft, bottomRight } = coveredEdges(map);
        map.fitBounds(bounds, {
          animate: false,
          paddingTopLeft: topLeft,
          paddingBottomRight: bottomRight,
        });
        fitted.current = true;
      }
    };
    const frame = requestAnimationFrame(refit);
    const observer = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    observer.observe(map.getContainer());
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [map, bounds]);

  // "all" draws the whole route in full whatever is selected; "dim" looks at it from the point
  const focusAt = view.mode === "all" ? -1 : markers.findIndex((m) => m.id === selectedId);
  const focus = focusAt < 0 ? null : focusAt;
  const { ahead, opacity } = view;
  const groups = useMemo(() => colorGroups(objects, visibleCats), [objects, visibleCats]);
  const icons = useMemo(() => iconGroups(objects, visibleCats), [objects, visibleCats]);

  // The draw data goes into the ref from a layout effect rather than straight from render:
  // Leaflet can trigger a redraw on its own — during a zoom animation frame, for one — and would
  // then read state React has not committed yet. A layout effect is guaranteed to run before the
  // redraw effect below.
  useLayoutEffect(() => {
    dataRef.current = { map, zMax, markers, focus, ahead, opacity, style, groups, icons, objects };
  });

  const setMapRef = useLatest(actions.setMap);

  useEffect(() => {
    // Take the function off the ref once: it is stable, and the lint rule is right to dislike
    // reading a ref in cleanup — by then it may hold something other than what we subscribed with.
    const report = setMapRef.current;
    const overlay = createCanvasOverlay((ctx, _project, drawBounds) => {
      if (dataRef.current) drawScene(ctx, drawBounds, dataRef.current, hoverRef.current);
    });
    overlay.addTo(map);
    overlayRef.current = overlay;
    report(map);
    return () => {
      overlay.remove();
      overlayRef.current = null;
      report(null);
    };
  }, [map, setMapRef]);

  // Redrawn when what the canvas shows changed. A label is not on it, and typing used to repaint
  // the whole canvas on every keystroke; a marker's colour is, since its leg takes it
  const drawn = useRef<Omit<SceneData, "map" | "objects"> | null>(null);
  useEffect(() => {
    const prev = drawn.current;
    drawn.current = { zMax, markers, focus, ahead, opacity, style, groups, icons };
    if (
      prev &&
      prev.zMax === zMax &&
      prev.focus === focus &&
      prev.ahead === ahead &&
      prev.opacity === opacity &&
      prev.style === style &&
      prev.groups === groups &&
      prev.icons === icons &&
      samePath(prev.markers, markers)
    ) {
      return;
    }
    overlayRef.current?.redraw();
  }, [zMax, markers, focus, ahead, opacity, style, groups, icons]);

  // The handlers are registered once and read the document through this ref: react-leaflet
  // re-subscribes whenever it is handed a new handlers object, which was every render
  const live = useLatest({ objects, visibleCats, markers, zMax, actions });

  const handlers = useMemo<LeafletEventHandlerFnMap>(() => {
    const pick = (latlng: LatLng) => {
      const { objects: index, visibleCats: visible, markers: route, zMax: z } = live.current;
      const p = toPoint(latlng);
      const radius = SNAP_PX / 2 ** (map.getZoom() - z);
      const object = index ? index.nearest(p.x, p.y, radius, visible) : null;
      const segment = nearestSegment(route, p, radius);
      return { point: p, object, segment };
    };

    const setHover = (next: Hover | null, at?: LeafletPoint) => {
      const tip = tipRef.current;
      if (tip) {
        const label = next && next.kind === "object" ? objectLabel(next.point) : "";
        if (label && at) {
          if (tip.textContent !== label) tip.textContent = label;
          tip.style.transform = `translate(${at.x + 14}px, ${at.y}px) translateY(-50%)`;
          tip.hidden = false;
        } else if (!tip.hidden) {
          tip.hidden = true;
        }
      }
      if (sameHover(hoverRef.current, next)) return;
      hoverRef.current = next;
      overlayRef.current?.redraw();
    };

    return {
      mousemove(e: LeafletMouseEvent) {
        // A held button is a pan or a marker drag: nothing is being pointed at, and picking on
        // every frame of it only added a full canvas redraw to each one
        if (e.originalEvent.buttons !== 0) {
          setHover(null);
          return;
        }
        const { object, segment } = pick(e.latlng);
        if (object) setHover({ kind: "object", point: object }, e.containerPoint);
        else if (segment) setHover({ kind: "segment", point: segment.point, index: segment.index });
        else setHover(null);
      },
      mouseout() {
        setHover(null);
      },
      click(e: LeafletMouseEvent) {
        const { objects: index, actions: act } = live.current;
        const { point, object, segment } = pick(e.latlng);
        const at = object ? { x: object.x, y: object.y } : point;
        const text = object ? objectLabel(object) : "";
        // the category color is only a suggestion: the editor decides whether to take it
        const color = object ? (index?.byId.get(object.cat)?.color ?? null) : null;
        if (segment) act.insertMarker(segment.index, at, text, color);
        else act.addMarker(at, text, color);
      },
    };
  }, [map, live]);

  useMapEvents(handlers);

  const last = markers.length - 1;
  const stacks = useMemo(() => stackOrder(markers), [markers]);

  return (
    <>
      {markers.map((m, i) => (
        <RouteMarker
          key={m.id}
          marker={m}
          number={i + 1}
          stack={stacks[i] ?? 0}
          // the points of the legs drawn in full: the one before the selected, and those ahead
          isFar={!isNearPoint(i, focus, ahead)}
          // a marker's own color outranks the "route end" teal that the `last` class paints
          color={m.color || style.color}
          isLast={!m.color && i === last && markers.length > 1}
          isSelected={selectedId === m.id}
        />
      ))}
      <div className="mo-tip" ref={tipRef} hidden aria-hidden="true" />
    </>
  );
}

export default function MapCanvas() {
  const { mapMeta } = useEditorState();
  const zMax = mapMeta ? mapMeta.tiles.zMax : 0;
  const zNative = mapMeta ? (mapMeta.tiles.zNative ?? zMax) : 0;
  // memoized on the numbers, not on the array: `mapMeta` arrives from Python as a new object with
  // every state, and the bounds would be rebuilt along with it ten times a second
  const [width, height]: [number, number] = mapMeta ? mapMeta.size : [0, 0];
  const crs = useMemo(() => pixelCRS(zMax), [zMax]);
  const bounds = useMemo(() => mapBounds([width, height]), [width, height]);

  // with no map selected the editor shows a placeholder and never gets here
  if (!mapMeta) return null;
  const url = `${mapMeta.tilesUrl}/{z}/{x}/{y}.jpg`;

  return (
    <MapContainer
      key={`${mapMeta.id}:${zMax}`}
      className="mo-map"
      crs={crs}
      bounds={bounds}
      maxBounds={bounds.pad(0.25)}
      maxBoundsViscosity={0.6}
      minZoom={Math.max(0, zMax - 4)}
      maxZoom={zMax + 3}
      zoomSnap={0}
      zoomDelta={ZOOM_STEP}
      // the wheel keeps every notch: see lib/smoothZoom
      scrollWheelZoom={false}
      smoothZoom
      zoomControl={false}
      attributionControl={false}
      doubleClickZoom={false}
    >
      <TileLayer
        // A new address remounts the layer rather than going through setUrl: Leaflet 1.9's
        // redraw() skips the rounding _setView does, and at the fractional zoom this map uses it
        // asked for tiles at z=1.64 -- none of which exist. The depth is in the key as well: a
        // pyramid cut again from a finer image keeps its address.
        key={`${url}:${zNative}`}
        url={url}
        tileSize={mapMeta.tiles.tile}
        maxNativeZoom={zNative}
        minNativeZoom={0}
        bounds={bounds}
        keepBuffer={4}
        noWrap
      />
      <Scene bounds={bounds} />
    </MapContainer>
  );
}
