import L from "leaflet";
import { describe, expect, it } from "vitest";

import { mapBounds, pixelCRS, toLatLng, toPoint } from "./crs";

// A deliberately asymmetric pixel: every assertion below would still pass on a swapped
// or mirrored implementation if x and y were equal.
const PX_X = 1280;
const PX_Y = 384;

describe("pixelCRS", () => {
  it("projects a map pixel onto itself at the top tile zoom", () => {
    for (const zMax of [3, 5]) {
      const point = pixelCRS(zMax).latLngToPoint(L.latLng(PX_Y, PX_X), zMax);
      expect(point.x).toBe(PX_X);
      expect(point.y).toBe(PX_Y);
    }
  });

  it("halves the coordinates one zoom level below the top", () => {
    const zMax = 4;
    const point = pixelCRS(zMax).latLngToPoint(L.latLng(PX_Y, PX_X), zMax - 1);
    expect(point.x).toBe(PX_X / 2);
    expect(point.y).toBe(PX_Y / 2);
  });

  it("scales by 2^(zoom - zMax) far below the top zoom", () => {
    const point = pixelCRS(5).latLngToPoint(L.latLng(PX_Y, PX_X), 2);
    expect(point.x).toBe(PX_X / 8);
    expect(point.y).toBe(PX_Y / 8);
  });

  it("maps a pixel back to the same latLng", () => {
    const zMax = 3;
    const crs = pixelCRS(zMax);
    const latlng = crs.pointToLatLng(L.point(PX_X, PX_Y), zMax);
    expect(latlng.lat).toBe(PX_Y);
    expect(latlng.lng).toBe(PX_X);
  });

  it("does not flip the Y axis the way CRS.Simple does", () => {
    const zMax = 3;
    const plain = L.CRS.Simple.latLngToPoint(L.latLng(PX_Y, PX_X), zMax);
    const pixel = pixelCRS(zMax).latLngToPoint(L.latLng(PX_Y, PX_X), zMax);
    expect(plain.y).toBeLessThan(0);
    expect(pixel.y).toBe(PX_Y);
  });

  it("keeps an infinite world so tile bounds are not clamped near the origin", () => {
    expect(pixelCRS(4).infinite).toBe(true);
  });

  it("does not mutate the shared L.CRS.Simple", () => {
    const zMax = 6;
    const latlng = L.latLng(PX_Y, PX_X);
    const before = L.CRS.Simple.latLngToPoint(latlng, zMax);
    pixelCRS(zMax);
    const after = L.CRS.Simple.latLngToPoint(latlng, zMax);
    expect({ x: after.x, y: after.y }).toEqual({ x: before.x, y: before.y });
  });
});

describe("toLatLng / toPoint", () => {
  it("puts the pixel Y in lat and the pixel X in lng", () => {
    const latlng = toLatLng(PX_X, PX_Y);
    expect(latlng.lat).toBe(PX_Y);
    expect(latlng.lng).toBe(PX_X);
  });

  it("round-trips a pixel without swapping the axes", () => {
    expect(toPoint(toLatLng(PX_X, PX_Y))).toEqual({ x: PX_X, y: PX_Y });
  });

  it("keeps negative and fractional pixels as they are", () => {
    expect(toPoint(toLatLng(-12.5, 7.25))).toEqual({ x: -12.5, y: 7.25 });
  });

  it("agrees with pixelCRS at the top zoom", () => {
    const zMax = 3;
    const point = pixelCRS(zMax).latLngToPoint(toLatLng(PX_X, PX_Y), zMax);
    expect({ x: point.x, y: point.y }).toEqual({ x: PX_X, y: PX_Y });
  });
});

describe("mapBounds", () => {
  const WIDTH = 100;
  const HEIGHT = 400;
  const bounds = mapBounds([WIDTH, HEIGHT]);

  it("anchors the south-west corner at pixel (0, 0)", () => {
    expect(bounds.getSouthWest().lat).toBe(0);
    expect(bounds.getSouthWest().lng).toBe(0);
  });

  it("puts the height in lat and the width in lng at the north-east corner", () => {
    expect(bounds.getNorthEast().lat).toBe(HEIGHT);
    expect(bounds.getNorthEast().lng).toBe(WIDTH);
  });

  it("contains a pixel inside the image", () => {
    expect(bounds.contains(toLatLng(50, 300))).toBe(true);
  });

  it("does not contain a pixel past the right edge", () => {
    expect(bounds.contains(toLatLng(WIDTH + 1, 300))).toBe(false);
  });

  it("does not contain a pixel past the bottom edge", () => {
    expect(bounds.contains(toLatLng(50, HEIGHT + 1))).toBe(false);
  });

  it("does not transpose a non-square size", () => {
    // (50, 300) fits a 100x400 image; (300, 50) only fits the transposed 400x100 one.
    expect(bounds.contains(toLatLng(50, 300))).toBe(true);
    expect(bounds.contains(toLatLng(300, 50))).toBe(false);
  });

  it("accepts the corner pixels themselves", () => {
    expect(bounds.contains(toLatLng(0, 0))).toBe(true);
    expect(bounds.contains(toLatLng(WIDTH, HEIGHT))).toBe(true);
  });

  it("degenerates to a single point for a zero-sized map", () => {
    const empty = mapBounds([0, 0]);
    expect(empty.getSouthWest().equals(empty.getNorthEast())).toBe(true);
    expect(empty.contains(toLatLng(0, 0))).toBe(true);
    expect(empty.contains(toLatLng(1, 0))).toBe(false);
  });
});
