import L from "leaflet";

import type { Point } from "./geometry";

/**
 * The coordinate system: Leaflet latitude/longitude = reference-map pixels.
 *
 * At tile level zMax the map lies at its original resolution, so the transformation scale is
 * 1/2^zMax: then latLng(y, x) is exactly pixel (x, y) of the map, and route coordinates never
 * have to be converted, neither when drawing nor when saving. A pyramid cut from a finer image
 * has levels past zMax; those only sharpen the picture. The Y axis is not flipped: on the image
 * it grows downwards too.
 */
export function pixelCRS(zMax: number): L.CRS {
  const s = 1 / 2 ** zMax;
  // infinite is left on: CRS.Simple states the world bounds in degrees (±180, ±90), and with
  // infinite: false Leaflet treats only a few tiles around zero as valid. The map's bounds are
  // set separately — by the bounds option of the tile layer and by the map's maxBounds.
  return L.extend({}, L.CRS.Simple, {
    transformation: new L.Transformation(s, 0, s, 0),
  });
}

/** Map pixel -> Leaflet point. */
export function toLatLng(x: number, y: number): L.LatLng {
  return L.latLng(y, x);
}

/** Leaflet point -> map pixel. */
export function toPoint(latlng: L.LatLng): Point {
  return { x: latlng.lng, y: latlng.lat };
}

/** The map's bounds for fitBounds and maxBounds. */
export function mapBounds(size: readonly [number, number]): L.LatLngBounds {
  return L.latLngBounds([0, 0], [size[1], size[0]]);
}
