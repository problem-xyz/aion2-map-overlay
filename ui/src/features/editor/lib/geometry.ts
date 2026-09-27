// Route geometry. The same maths as the Python overlay (overlay.py), so the route looks the same
// in the editor and over the game.

/** A point in pixels: map pixels for route coordinates, screen pixels once projected. */
export interface Point {
  x: number;
  y: number;
}

export const ARROW_L = 14;
export const ARROW_W = 12;
export const MIN_SEGMENT = 2 * ARROW_L;
export const SNAP_PX = 9; // how many pixels from an object or a line the hint fires at
// Away from the selected point the route is drawn faded, at this share of its opacity, and
// without arrows. Drawn all alike, a route that loops about a village was a tangle nobody could
// read the way on from.
export const FAR_OPACITY = 0.3;

/**
 * Whether leg `i` (from point i to point i + 1) is drawn in full while the route is looked at
 * from point `focus`, `ahead` steps of it: the first is the leg into the point, as the leg
 * being walked is over the game. With no focus, every leg is.
 */
export function isNearLeg(i: number, focus: number | null, ahead: number): boolean {
  return focus === null || (i >= focus - 1 && i < focus - 1 + ahead);
}

/** Whether point `i` is an end of one of those legs, and so drawn in full with them. */
export function isNearPoint(i: number, focus: number | null, ahead: number): boolean {
  return focus === null || (i >= focus - 1 && i <= focus - 1 + ahead);
}

/**
 * The arrow in the middle of a segment: its tip, then the ends of its two wings -- the canvas
 * strokes them as a chevron. null — the segment is too short.
 */
export function arrowPolygon(
  a: Point,
  b: Point,
  len: number = ARROW_L,
  width: number = ARROW_W,
): [Point, Point, Point] | null {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length = Math.hypot(dx, dy);
  if (length < MIN_SEGMENT) return null;
  const ux = dx / length;
  const uy = dy / length;
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const back = { x: mx - (ux * len) / 2, y: my - (uy * len) / 2 };
  return [
    { x: mx + (ux * len) / 2, y: my + (uy * len) / 2 },
    { x: back.x - (uy * width) / 2, y: back.y + (ux * width) / 2 },
    { x: back.x + (uy * width) / 2, y: back.y - (ux * width) / 2 },
  ];
}

export interface SegmentHit {
  distance: number;
  /** The closest point on the segment. */
  point: Point;
  /** Where it lies on the segment: 0 — the start, 1 — the end. */
  t: number;
}

export function distanceToSegment(p: Point, a: Point, b: Point): SegmentHit {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  let t = len2 === 0 ? 0 : ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
  t = Math.max(0, Math.min(1, t));
  const point = { x: a.x + t * dx, y: a.y + t * dy };
  return { distance: Math.hypot(p.x - point.x, p.y - point.y), point, t };
}

export interface NearestSegment {
  /** Index of the segment's start: a point is inserted after it. */
  index: number;
  point: Point;
  distance: number;
}

export function nearestSegment(
  points: readonly Point[],
  p: Point,
  maxDistance: number,
): NearestSegment | null {
  let best: NearestSegment | null = null;
  for (let i = 0; i < points.length - 1; i += 1) {
    // i stops short of the last index, so both ends of the segment are there
    const hit = distanceToSegment(p, points[i]!, points[i + 1]!);
    if (hit.distance <= maxDistance && (!best || hit.distance < best.distance)) {
      best = { index: i, point: hit.point, distance: hit.distance };
    }
  }
  return best;
}
