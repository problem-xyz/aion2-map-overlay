import L from "leaflet";

/** Projects a Leaflet point into layer coordinates — the same thing the renderer itself does. */
export type Project = (latlng: L.LatLng) => L.Point;

/** What to draw. Called on every frame: pan, zoom, a change of data. */
export type DrawFn = (ctx: CanvasRenderingContext2D, project: Project, bounds: L.Bounds) => void;

export interface CanvasOverlayOptions extends L.RendererOptions {
  draw?: DrawFn;
}

export interface CanvasOverlayLayer extends L.Renderer {
  redraw(): void;
}

/**
 * Internal L.Renderer fields: @types/leaflet does not declare them, and there is no drawing
 * without them. A separate type, so that `this` inside the methods stays checkable; it cannot
 * extend `L.Renderer` — `_map` is declared protected there.
 */
interface Internals {
  _map: L.Map & { _animatingZoom?: boolean };
  _bounds: L.Bounds;
  // optional, because _destroyContainer deletes them
  _container?: HTMLCanvasElement;
  _ctx?: CanvasRenderingContext2D | null;
  _frame: number | null;
  _drawFn: DrawFn | null;
  _render(): void;
  redraw(): void;
}

/**
 * The constructor from `L.Renderer.extend`: in Leaflet's types it loses both its parameters and
 * our `redraw`.
 */
type CanvasOverlayCtor = new (options?: CanvasOverlayOptions) => CanvasOverlayLayer;

/** The base methods we override and call — Leaflet's types do not have them either. */
const base = L.Renderer.prototype as unknown as {
  initialize(this: Internals, options?: L.RendererOptions): void;
  _update(this: Internals): void;
};

/**
 * One canvas over the tiles: the map's objects and the route line with its arrows.
 *
 * We extend L.Renderer, so positioning, the zoom animation and the padding around the edges come
 * ready-made and proven. We draw in layer coordinates (layer point) — those are screen pixels, so
 * line thickness and marker size do not depend on the zoom. There are no DOM elements per object:
 * fifteen hundred points are a single pass over an array.
 */
const CanvasOverlay = L.Renderer.extend({
  options: {
    padding: 0.4, // slack around the screen, so the edges do not go blank while dragging
  },

  initialize(this: Internals, options?: CanvasOverlayOptions) {
    base.initialize.call(this, options);
    this._drawFn = options?.draw ?? null;
  },

  redraw(this: Internals) {
    if (!this._map) return;
    if (this._frame) return;
    this._frame = L.Util.requestAnimFrame(() => {
      this._frame = null;
      this._render();
    }, this);
  },

  _initContainer(this: Internals) {
    const container = (this._container = document.createElement("canvas"));
    container.className = "mo-canvas";
    container.style.pointerEvents = "none";
    this._ctx = container.getContext("2d");
  },

  _destroyContainer(this: Internals) {
    if (this._frame !== null) L.Util.cancelAnimFrame(this._frame);
    this._frame = null;
    delete this._ctx;
    L.DomUtil.remove(this._container as HTMLCanvasElement);
    delete this._container;
  },

  // L.Renderer subscribes to the update event to redraw its own paths — we have none
  _updatePaths() {},

  _update(this: Internals) {
    if (this._map._animatingZoom && this._bounds) return;
    base._update.call(this);

    const bounds = this._bounds;
    const min = bounds.min as L.Point;
    const size = bounds.getSize();
    const ratio = window.devicePixelRatio || 1;
    const container = this._container as HTMLCanvasElement;

    L.DomUtil.setPosition(container, min);
    // Assigning width or height reallocates the bitmap even when the value is the same, and a
    // pan ends here every time. At 1.8x the viewport and a 1.5 device ratio that was a fresh
    // 25 MB canvas per pan; now only a resize or a zoom that changes the size pays for it.
    const width = Math.round(ratio * size.x);
    const height = Math.round(ratio * size.y);
    if (container.width !== width || container.height !== height) {
      container.width = width;
      container.height = height;
      container.style.width = `${size.x}px`;
      container.style.height = `${size.y}px`;
    }

    // Set, not multiplied onto what is there: the canvas keeps its context between pans now,
    // and the offset changes with every one of them
    this._ctx?.setTransform(ratio, 0, 0, ratio, -min.x * ratio, -min.y * ratio);
    this._render();
  },

  _render(this: Internals) {
    if (!this._ctx || !this._bounds || !this._drawFn) return;
    const ctx = this._ctx;
    const bounds = this._bounds;
    const min = bounds.min as L.Point;
    const size = bounds.getSize();
    ctx.clearRect(min.x, min.y, size.x, size.y);
    ctx.save();
    this._drawFn(ctx, (latlng) => this._map.latLngToLayerPoint(latlng), bounds);
    ctx.restore();
  },
}) as unknown as CanvasOverlayCtor;

export default function createCanvasOverlay(draw: DrawFn): CanvasOverlayLayer {
  return new CanvasOverlay({ draw });
}
