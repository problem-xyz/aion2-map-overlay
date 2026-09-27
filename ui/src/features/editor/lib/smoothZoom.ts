import L from "leaflet";

/** One wheel notch, and one press of a zoom button: the same step either way. */
export const ZOOM_STEP = 0.5;

// A notch as QtWebEngine delivers it: Qt's 3 lines of 20 px, in device pixels. The page divides
// that by its zoom factor, so deltaY alone would scroll slower on a larger desktop scale.
const NOTCH_PX = 60;
const LINE_PX = 20;
const PAGE_PX = NOTCH_PX * 2;
// No single event may jump further than this, whatever a driver reports
const MAX_EVENT_LEVELS = 1;
const SETTLE_LEVELS = 0.001;
// Leaflet animates at most this many levels at once (zoomAnimationThreshold) and jumps past it
const HOP_LEVELS = 4;

/** Zoom levels a wheel event asks for: positive zooms in. */
export function wheelLevels(deltaY: number, deltaMode: number, ratio: number): number {
  const px = deltaMode === 0 ? deltaY * ratio : deltaY * (deltaMode === 1 ? LINE_PX : PAGE_PX);
  const levels = (-px / NOTCH_PX) * ZOOM_STEP;
  return Math.max(-MAX_EVENT_LEVELS, Math.min(MAX_EVENT_LEVELS, levels));
}

/** Where a zoom that is at `zoom` and was sent to `target` goes in one animation. */
export function nextHop(zoom: number, target: number, limit: number): number | null {
  const left = target - zoom;
  if (Math.abs(left) < SETTLE_LEVELS) return null;
  return zoom + Math.max(-limit, Math.min(limit, left));
}

/** How long Leaflet's zoom animation runs here: editor.css sets it to --duration-enter. */
function animationMs(): number {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return 0;
  const value = getComputedStyle(document.documentElement).getPropertyValue("--duration-enter");
  return Number.parseFloat(value) || 200;
}

/** Map internals the zoom drives: those of Leaflet's own animated zoom. */
interface MapInternals {
  _animatingZoom?: boolean;
  _animateZoom(center: L.LatLng, zoom: number, startAnim: boolean): void;
  _onZoomTransitionEnd(): void;
  _limitCenter(center: L.LatLng, zoom: number, bounds?: L.LatLngBoundsExpression): L.LatLng;
}

/**
 * Wheel zoom that keeps every notch and answers each one at once, played as Leaflet's own CSS
 * zoom animation.
 *
 * Leaflet's wheel zoom dropped the notches that came while an animation played, so a quick spin
 * lost most of itself, and it asked about a tenth of a level per notch of QtWebEngine's wheel.
 * Here a notch moves a target by ZOOM_STEP. With no animation playing, Leaflet starts one; with
 * one playing, it is sent on to the new target, and the transitions carry on from wherever the
 * map is at that moment. The map lands one animation after the last notch.
 *
 * It glided once, moving the map a little every frame through `_move`. That redrew the tiles at
 * a new scale and the whole canvas on every frame, and under that load QtWebEngine put frames on
 * screen half drawn -- black staircases, the page blinking -- even through OpenGL. Leaflet's
 * animation is CSS transitions the compositor plays on its own, with nothing redrawn until it
 * lands. Sending one on is the same `_animateZoom` call that started it; only the end is taken
 * over, since Leaflet ends every animation 250ms after it began, however far it still had to go.
 */
export class SmoothZoom extends L.Handler {
  private readonly map: L.Map;
  private readonly inner: MapInternals;
  private target: number | null = null;
  private anchor: L.Point | null = null;
  // From asking Leaflet for an animation until its zoomend. Leaflet starts it a frame later, so
  // its own _animatingZoom is still false for notches that come in that frame.
  private busy = false;
  // Not before then does the animation end, whatever a timer of Leaflet's says
  private endsAt = 0;
  private leafletEnd: (() => void) | null = null;

  constructor(map: L.Map) {
    super(map);
    this.map = map;
    this.inner = map as unknown as MapInternals;
  }

  addHooks(): void {
    this.map.getContainer().addEventListener("wheel", this.onWheel, { passive: false });
    this.map.on("zoomanim", this.onZoomAnim);
    this.map.on("zoomend", this.onZoomEnd);
    this.map.on("dragstart", this.onDragStart);
    // Leaflet's end, held back until the last animation sent on has run its course; the
    // transitionend of that one, and the timer set with it, still reach it
    const end = this.inner._onZoomTransitionEnd.bind(this.map);
    this.leafletEnd = end;
    this.inner._onZoomTransitionEnd = () => {
      if (performance.now() >= this.endsAt) end();
    };
  }

  removeHooks(): void {
    this.map.getContainer().removeEventListener("wheel", this.onWheel);
    this.map.off("zoomanim", this.onZoomAnim);
    this.map.off("zoomend", this.onZoomEnd);
    this.map.off("dragstart", this.onDragStart);
    if (this.leafletEnd) this.inner._onZoomTransitionEnd = this.leafletEnd;
    this.leafletEnd = null;
    this.stop();
  }

  /** Zoom by `levels` around a container point -- the cursor -- or the middle of the map. */
  zoomBy(levels: number, around?: L.Point): void {
    const map = this.map;
    // during an animation getZoom() is already where it is headed
    const base = this.target ?? map.getZoom();
    this.target = Math.max(map.getMinZoom(), Math.min(map.getMaxZoom(), base + levels));
    this.anchor = around ?? null;
    if (this.inner._animatingZoom) this.sendOn();
    else if (!this.busy) this.start();
  }

  /** Forget the notches still waiting: something else moves the map now. */
  stop(): void {
    this.target = null;
    this.anchor = null;
  }

  private around(): L.Point {
    return this.anchor ?? this.map.getSize().divideBy(2);
  }

  private start(): void {
    const map = this.map;
    const next = this.target === null ? null : nextHop(map.getZoom(), this.target, HOP_LEVELS);
    if (next === null) {
      this.stop();
      return;
    }
    this.busy = true;
    map.setZoomAround(this.around(), next, { animate: true });
  }

  /** Point the animation that is playing at the new target, the anchor held where it is. */
  private sendOn(): void {
    const map = this.map;
    const next = this.target === null ? null : nextHop(map.getZoom(), this.target, HOP_LEVELS);
    if (next === null) return;
    const around = this.around();
    const offset = around.subtract(map.getSize().divideBy(2));
    // the anchor's place on the map where the running animation will land, kept under it
    const at = map.containerPointToLatLng(around);
    const center = this.inner._limitCenter(
      map.unproject(map.project(at, next).subtract(offset), next),
      next,
      map.options.maxBounds,
    );
    this.endsAt = performance.now() + animationMs() - 16;
    this.inner._animateZoom(center, next, true);
  }

  private readonly onZoomAnim = (e: L.ZoomAnimEvent): void => {
    // Notches that came before Leaflet started the animation, a frame after it was asked for.
    // Sent on after this event has reached every layer, so it goes out in the same frame.
    if (this.target !== null && Math.abs(this.target - e.zoom) > SETTLE_LEVELS) {
      queueMicrotask(() => {
        if (this.inner._animatingZoom) this.sendOn();
      });
    }
  };

  private readonly onZoomEnd = (): void => {
    this.busy = false;
    this.endsAt = 0;
    // a target past one animation's reach, or notches that came as it ended
    if (this.target !== null) this.start();
  };

  private readonly onDragStart = (): void => {
    this.stop();
  };

  private readonly onWheel = (e: WheelEvent): void => {
    e.preventDefault();
    const levels = wheelLevels(e.deltaY, e.deltaMode, window.devicePixelRatio || 1);
    if (levels) this.zoomBy(levels, this.map.mouseEventToContainerPoint(e));
  };
}

declare module "leaflet" {
  interface MapOptions {
    /** The wheel zoom above; set `scrollWheelZoom: false` beside it. */
    smoothZoom?: boolean;
  }
  interface Map {
    smoothZoom?: SmoothZoom;
  }
}

L.Map.addInitHook("addHandler", "smoothZoom", SmoothZoom);
