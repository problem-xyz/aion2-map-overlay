/**
 * The wheel zoom: how far a wheel event asks to go, and how far one animation takes it there.
 */

import { describe, expect, it } from "vitest";

import { ZOOM_STEP, nextHop, wheelLevels } from "./smoothZoom";

describe("wheelLevels", () => {
  it("makes one notch of QtWebEngine's wheel one zoom step, at any desktop scale", () => {
    // what the editor page receives per notch: 60 device px divided by the page's zoom factor
    expect(wheelLevels(-40, 0, 1.5)).toBeCloseTo(ZOOM_STEP);
    expect(wheelLevels(-60, 0, 1)).toBeCloseTo(ZOOM_STEP);
    expect(wheelLevels(-30, 0, 2)).toBeCloseTo(ZOOM_STEP);
  });

  it("zooms in on a wheel turned away, out on one turned back", () => {
    expect(wheelLevels(-40, 0, 1.5)).toBeGreaterThan(0);
    expect(wheelLevels(40, 0, 1.5)).toBeLessThan(0);
  });

  it("follows a touchpad's small deltas in proportion", () => {
    expect(wheelLevels(-4, 0, 1.5)).toBeCloseTo(ZOOM_STEP / 10);
  });

  it("reads line and page deltas too, and caps what one event can ask for", () => {
    expect(wheelLevels(-3, 1, 1.5)).toBeCloseTo(ZOOM_STEP);
    expect(wheelLevels(-1, 2, 1.5)).toBeCloseTo(1);
    expect(wheelLevels(-5000, 0, 1.5)).toBe(1);
    expect(wheelLevels(5000, 0, 1.5)).toBe(-1);
  });
});

describe("nextHop", () => {
  it("goes the whole way when it is within one animation", () => {
    expect(nextHop(3, 5.5, 4)).toBe(5.5);
    expect(nextHop(5, 2, 4)).toBe(2);
  });

  it("stops at the animation's limit, and leaves the rest to the next hop", () => {
    // Leaflet jumps rather than animates past zoomAnimationThreshold
    expect(nextHop(0, 7, 4)).toBe(4);
    expect(nextHop(7, 0, 4)).toBe(3);
  });

  it("has nowhere to go once it has arrived", () => {
    expect(nextHop(4, 4, 4)).toBeNull();
    expect(nextHop(4, 4.0004, 4)).toBeNull();
  });
});
