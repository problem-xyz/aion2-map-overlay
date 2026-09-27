import { describe, expect, it } from "vitest";

import {
  ARROW_L,
  ARROW_W,
  MIN_SEGMENT,
  arrowPolygon,
  distanceToSegment,
  isNearLeg,
  isNearPoint,
  nearestSegment,
  type Point,
} from "./geometry";

const PRECISION = 9;

/** Unwraps a result the test expects to exist: a missing one has to fail loudly, not silently. */
function must<T>(value: T | null): T {
  if (value === null) throw new Error("expected a value, got null");
  return value;
}

function expectPoint(actual: Point, expected: Point): void {
  expect(actual.x).toBeCloseTo(expected.x, PRECISION);
  expect(actual.y).toBeCloseTo(expected.y, PRECISION);
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function midpoint(a: Point, b: Point): Point {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

describe("arrowPolygon", () => {
  it("returns null just below the MIN_SEGMENT threshold", () => {
    expect(arrowPolygon({ x: 0, y: 0 }, { x: 0, y: MIN_SEGMENT - 0.001 })).toBeNull();
  });

  it("returns a triangle at exactly MIN_SEGMENT, so the threshold is not exclusive", () => {
    const tri = arrowPolygon({ x: 0, y: 0 }, { x: 0, y: MIN_SEGMENT });

    expect(tri).not.toBeNull();
    expect(tri).toHaveLength(3);
  });

  it("returns null for a segment with both ends in the same place", () => {
    expect(arrowPolygon({ x: 7, y: 7 }, { x: 7, y: 7 })).toBeNull();
  });

  it("points the arrow towards the second endpoint on a horizontal segment", () => {
    const tri = must(arrowPolygon({ x: 0, y: 0 }, { x: 40, y: 0 }));

    expectPoint(tri[0], { x: 27, y: 0 });
    expectPoint(tri[1], { x: 13, y: 6 });
    expectPoint(tri[2], { x: 13, y: -6 });
  });

  it("points the arrow towards the second endpoint on a vertical segment", () => {
    const tri = must(arrowPolygon({ x: 0, y: 0 }, { x: 0, y: 40 }));

    expectPoint(tri[0], { x: 0, y: 27 });
    expectPoint(tri[1], { x: -6, y: 13 });
    expectPoint(tri[2], { x: 6, y: 13 });
  });

  it("points the arrow along a diagonal segment rather than along an axis", () => {
    const tri = must(arrowPolygon({ x: 0, y: 0 }, { x: 60, y: 80 }));

    expectPoint(tri[0], { x: 34.2, y: 45.6 });
    expectPoint(tri[1], { x: 21, y: 38 });
    expectPoint(tri[2], { x: 30.6, y: 30.8 });
  });

  it("moves the tip to the other side of the midpoint when the endpoints are swapped", () => {
    const a = { x: 10, y: 20 };
    const b = { x: 70, y: 100 };

    const forward = must(arrowPolygon(a, b));
    const backward = must(arrowPolygon(b, a));

    expectPoint(forward[0], { x: 44.2, y: 65.6 });
    expectPoint(backward[0], { x: 35.8, y: 54.4 });
    expectPoint(midpoint(forward[0], backward[0]), midpoint(a, b));
  });

  it("puts the tip on the segment itself, between the endpoints", () => {
    const a = { x: -30, y: 12 };
    const b = { x: 50, y: 72 };

    const hit = distanceToSegment(must(arrowPolygon(a, b))[0], a, b);

    expect(hit.distance).toBeCloseTo(0, PRECISION);
    expect(hit.t).toBeGreaterThan(0);
    expect(hit.t).toBeLessThan(1);
  });

  it("centres the arrow on the segment midpoint", () => {
    const a = { x: 4, y: -6 };
    const b = { x: 104, y: 44 };
    const tri = must(arrowPolygon(a, b));

    expectPoint(midpoint(tri[0], midpoint(tri[1], tri[2])), midpoint(a, b));
  });

  it("makes the base ARROW_W wide and the arrow ARROW_L long by default", () => {
    const tri = must(arrowPolygon({ x: 0, y: 0 }, { x: 60, y: 80 }));

    expect(distance(tri[1], tri[2])).toBeCloseTo(ARROW_W, PRECISION);
    expect(distance(tri[0], midpoint(tri[1], tri[2]))).toBeCloseTo(ARROW_L, PRECISION);
  });

  it("honours custom len and width arguments", () => {
    const tri = must(arrowPolygon({ x: 0, y: 0 }, { x: 40, y: 0 }, 20, 4));

    expectPoint(tri[0], { x: 30, y: 0 });
    expectPoint(tri[1], { x: 10, y: 2 });
    expectPoint(tri[2], { x: 10, y: -2 });
    expect(distance(tri[1], tri[2])).toBeCloseTo(4, PRECISION);
    expect(distance(tri[0], midpoint(tri[1], tri[2]))).toBeCloseTo(20, PRECISION);
  });

  it("mirrors the two base vertices across the segment axis", () => {
    const a = { x: 0, y: 0 };
    const b = { x: 60, y: 80 };
    const mid = midpoint(a, b);
    const ux = 0.6;
    const uy = 0.8;
    const across = (q: Point): number => ux * (q.y - mid.y) - uy * (q.x - mid.x);
    const along = (q: Point): number => ux * (q.x - mid.x) + uy * (q.y - mid.y);
    const tri = must(arrowPolygon(a, b));

    expect(across(tri[0])).toBeCloseTo(0, PRECISION);
    expect(across(tri[1])).toBeCloseTo(ARROW_W / 2, PRECISION);
    expect(across(tri[2])).toBeCloseTo(-ARROW_W / 2, PRECISION);
    expect(along(tri[1])).toBeCloseTo(along(tri[2]), PRECISION);
  });

  it("keeps the MIN_SEGMENT threshold whatever len is asked for", () => {
    expect(arrowPolygon({ x: 0, y: 0 }, { x: 30, y: 0 }, 200, 4)).not.toBeNull();
    expect(arrowPolygon({ x: 0, y: 0 }, { x: 20, y: 0 }, 4, 2)).toBeNull();
  });
});

describe("distanceToSegment", () => {
  it("clamps to the start when the point lies behind it", () => {
    const hit = distanceToSegment({ x: -10, y: 0 }, { x: 0, y: 0 }, { x: 10, y: 0 });

    expect(hit.t).toBe(0);
    expectPoint(hit.point, { x: 0, y: 0 });
    expect(hit.distance).toBeCloseTo(10, PRECISION);
  });

  it("clamps to the end when the point lies past it", () => {
    const hit = distanceToSegment({ x: 20, y: 5 }, { x: 0, y: 0 }, { x: 10, y: 0 });

    expect(hit.t).toBe(1);
    expectPoint(hit.point, { x: 10, y: 0 });
    expect(hit.distance).toBeCloseTo(Math.hypot(10, 5), PRECISION);
  });

  it("drops a perpendicular when the foot falls inside the segment", () => {
    const hit = distanceToSegment({ x: 3, y: 4 }, { x: 0, y: 0 }, { x: 10, y: 0 });

    expect(hit.t).toBeCloseTo(0.3, PRECISION);
    expectPoint(hit.point, { x: 3, y: 0 });
    expect(hit.distance).toBeCloseTo(4, PRECISION);
  });

  it("measures the perpendicular, not the distance to the nearer endpoint", () => {
    const hit = distanceToSegment({ x: 10, y: 0 }, { x: 0, y: 0 }, { x: 10, y: 10 });

    expect(hit.t).toBeCloseTo(0.5, PRECISION);
    expectPoint(hit.point, { x: 5, y: 5 });
    expect(hit.distance).toBeCloseTo(Math.SQRT2 * 5, PRECISION);
  });

  it("reports zero distance for a point lying on the segment", () => {
    const hit = distanceToSegment({ x: 2, y: 2 }, { x: 0, y: 0 }, { x: 10, y: 10 });

    expect(hit.distance).toBeCloseTo(0, PRECISION);
    expect(hit.t).toBeCloseTo(0.2, PRECISION);
  });

  it("collapses a zero-length segment to its single point instead of dividing by zero", () => {
    const hit = distanceToSegment({ x: 8, y: 9 }, { x: 5, y: 5 }, { x: 5, y: 5 });

    expect(hit.t).toBe(0);
    expectPoint(hit.point, { x: 5, y: 5 });
    expect(hit.distance).toBeCloseTo(5, PRECISION);
    expect(Number.isNaN(hit.distance)).toBe(false);
  });
});

describe("nearestSegment", () => {
  const path: Point[] = [
    { x: 0, y: 0 },
    { x: 100, y: 0 },
    { x: 100, y: 100 },
    { x: 0, y: 100 },
  ];

  it("picks the closest segment, not the first one within range", () => {
    const hit = must(nearestSegment(path, { x: 95, y: 40 }, 50));

    expect(hit.index).toBe(1);
    expectPoint(hit.point, { x: 100, y: 40 });
    expect(hit.distance).toBeCloseTo(5, PRECISION);
  });

  it("reports the index of the segment's first point, where a new marker is spliced in", () => {
    const hit = must(nearestSegment(path, { x: 50, y: 104 }, 10));

    expect(hit.index).toBe(2);
    expectPoint(hit.point, { x: 50, y: 100 });
  });

  it("returns null when every segment is farther away than maxDistance", () => {
    expect(nearestSegment(path, { x: 50, y: 40 }, 10)).toBeNull();
  });

  it("counts a segment lying exactly maxDistance away", () => {
    const line: Point[] = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
    ];

    expect(must(nearestSegment(line, { x: 5, y: 3 }, 3)).distance).toBeCloseTo(3, PRECISION);
    expect(nearestSegment(line, { x: 5, y: 3 }, 2.9)).toBeNull();
  });

  it("keeps the earlier segment when two are equally close", () => {
    const bend: Point[] = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 20, y: 0 },
    ];

    const hit = must(nearestSegment(bend, { x: 10, y: 5 }, 10));

    expect(hit.index).toBe(0);
    expectPoint(hit.point, { x: 10, y: 0 });
  });

  it("clamps to an endpoint when the point lies beyond the end of the path", () => {
    const hit = must(nearestSegment(path, { x: -4, y: 103 }, 10));

    expect(hit.index).toBe(2);
    expectPoint(hit.point, { x: 0, y: 100 });
    expect(hit.distance).toBeCloseTo(5, PRECISION);
  });

  it("returns null when there is no segment to hit", () => {
    expect(nearestSegment([], { x: 0, y: 0 }, 1000)).toBeNull();
    expect(nearestSegment([{ x: 0, y: 0 }], { x: 0, y: 0 }, 1000)).toBeNull();
  });

  it("accepts route markers carrying fields beside x and y", () => {
    interface Marker extends Point {
      id: string;
      color: string;
    }

    const markers: Marker[] = [
      { x: 0, y: 0, id: "a", color: "#ffffff" },
      { x: 40, y: 0, id: "b", color: "#000000" },
    ];

    const hit = must(nearestSegment(markers, { x: 10, y: 2 }, 5));

    expect(hit.index).toBe(0);
    expect(hit.point).toEqual({ x: 10, y: 0 });
  });
});

describe("isNearLeg", () => {
  it("draws every leg in full while no point is selected", () => {
    expect([0, 1, 5, 40].every((i) => isNearLeg(i, null, 3))).toBe(true);
  });

  it("draws the leg into the selected point and the steps after it, and no others", () => {
    const legs = Array.from({ length: 12 }, (_, i) => i);

    // three steps: leg 4 comes into point 5, legs 5 and 6 lead on from it
    expect(legs.filter((i) => isNearLeg(i, 5, 3))).toEqual([4, 5, 6]);
    expect(legs.filter((i) => isNearLeg(i, 5, 1))).toEqual([4]);
  });

  it("keeps the points at the ends of those legs in full", () => {
    const points = Array.from({ length: 12 }, (_, i) => i);

    expect(points.filter((i) => isNearPoint(i, 5, 3))).toEqual([4, 5, 6, 7]);
    // the first point has no leg into it: one step from it is that point alone
    expect(points.filter((i) => isNearPoint(i, 0, 1))).toEqual([0]);
  });
});
