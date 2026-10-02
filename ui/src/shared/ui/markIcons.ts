/**
 * The small drawings the map and its lists use for what a point is: the object categories the
 * game gives an icon of its own -- a feather for the Empyrean Traces, a winged crest for the
 * teleports (a blue winged figure on the Elyos map), a question mark for the seals, a coral cube
 * for the hidden cubes, one of its own for each gathering resource (resourceMarks.ts) -- and the
 * two quest stars a route point can be given, yellow for a main quest and green for a side one.
 *
 * Drawn here rather than taken from the game, whose art is NCSoft's and stays out of this
 * repository: after the client's icons in shape and colour, not copies of them. One drawing
 * serves the map, as a bitmap made once per size, and the lists, as an SVG. Shared, because the
 * editor and the steps plaque both draw them.
 */

import type { MarkerIcon } from "@/shared/backend/contract";

import { isResourceIcon, resourceLayers, type ResourceIconName } from "./resourceMarks";

type DrawnIconName = "trace" | "teleport" | "teleportElyos" | "seal" | "cube";
export type ObjectIconName = DrawnIconName | ResourceIconName;
export type QuestIconName = "questMain" | "questSide";
export type MarkIconName = ObjectIconName | QuestIconName;

/** The star a route point's icon field names. */
export function questIcon(icon: MarkerIcon): QuestIconName {
  return icon === "main" ? "questMain" : "questSide";
}

// A four-pointed star with slightly hollow sides, and the smaller face inside it
const STAR = "M12 1.5Q15.3 8.7 22.5 12Q15.3 15.3 12 22.5Q8.7 15.3 1.5 12Q8.7 8.7 12 1.5Z";
const STAR_FACE = "M12 5.6Q13.8 10.2 18.4 12Q13.8 13.8 12 18.4Q10.2 13.8 5.6 12Q10.2 10.2 12 5.6Z";

/** One pass of a drawing on a 24px grid: a path filled, stroked, or both, fill first. */
export interface IconLayer {
  d: string;
  fill?: string;
  stroke?: string;
  width?: number;
}

const INK = "#15171c";

type Vec = readonly [number, number];

/**
 * A circle on one face of the cube, as a path: the face's two edges, `a` and `b` from its corner
 * `origin`, carry the circle into the picture, so it lies on the face at the face's own slant.
 */
function faceRing(origin: Vec, a: Vec, b: Vec, r: number): string {
  let d = "";
  for (let i = 0; i < 20; i += 1) {
    const angle = (i / 20) * Math.PI * 2;
    const s = 0.5 + r * Math.cos(angle);
    const t = 0.5 + r * Math.sin(angle);
    const x = origin[0] + s * a[0] + t * b[0];
    const y = origin[1] + s * a[1] + t * b[1];
    d += `${i === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  return `${d}Z`;
}

/** The spokes of a face's wheel, as `count` diameters across it, laid on the face as faceRing. */
function faceSpokes(origin: Vec, a: Vec, b: Vec, r: number, count: number): string {
  const at = (s: number, t: number) =>
    `${(origin[0] + s * a[0] + t * b[0]).toFixed(2)} ${(origin[1] + s * a[1] + t * b[1]).toFixed(2)}`;
  let d = "";
  for (let i = 0; i < count; i += 1) {
    const angle = (i / count) * Math.PI;
    const s = r * Math.cos(angle);
    const t = r * Math.sin(angle);
    d += `M${at(0.5 + s, 0.5 + t)}L${at(0.5 - s, 0.5 - t)}`;
  }
  return d;
}

// The cube's three faces, each as its corner and its two edges on the 24px grid
const TOP: [Vec, Vec, Vec] = [
  [3.5, 7.2],
  [8.5, -4.7],
  [8.5, 4.7],
];
const LEFT: [Vec, Vec, Vec] = [
  [3.5, 7.2],
  [8.5, 4.7],
  [0, 9.6],
];
const RIGHT: [Vec, Vec, Vec] = [
  [12, 11.9],
  [8.5, -4.7],
  [0, 9.6],
];
const FACES = [TOP, LEFT, RIGHT];
const CUBE_INK = "#3a0c08";
const CUBE_WHEEL = "#ffd6cb";

const ICONS: Record<DrawnIconName | QuestIconName, readonly IconLayer[]> = {
  // a pale feather, quill to the lower left
  trace: [
    {
      d: "M20 3.2c-6.3.2-11.4 4-13.1 10.2l-1.1 4.4 1 1 3.4-2.5C16 14.8 19.7 9.8 20 3.2Z",
      fill: "#f4f0e6",
      stroke: INK,
      width: 1.3,
    },
    { d: "M20 3.2c-3.9 3.3-7.6 7.7-10.3 13", stroke: "#b3aa98", width: 1.1 },
    { d: "M4 20.6l3.3-3.6", stroke: INK, width: 1.8 },
  ],
  // a violet crest, pointed below, between two wings swept up
  teleport: [
    {
      d:
        "M10.4 10.8C8.9 7.4 5.9 4.7 2 3.6c.2 3.8 2 7.1 5.1 8.6 1.1.5 2.2.6 3.3.4Z" +
        "M13.6 10.8c1.5-3.4 4.5-6.1 8.4-7.2-.2 3.8-2 7.1-5.1 8.6-1.1.5-2.2.6-3.3.4Z",
      fill: "#c79bf7",
      stroke: "#1b1026",
      width: 1.2,
    },
    {
      d: "M12 6.6l3.5 2.7v5.4L12 21.2l-3.5-6.5V9.3Z",
      fill: "#8f4fe0",
      stroke: "#1b1026",
      width: 1.2,
    },
    { d: "M12 9.2v8.2", stroke: "#e9d7ff", width: 1 },
  ],
  // a pale blue winged figure over a shield, the Elyos teleport
  teleportElyos: [
    {
      d:
        "M10.6 9.6C9.1 6.4 6.2 4.1 2.3 3.2c.1 3.8 1.9 7.2 5 8.8 1.1.6 2.2.8 3.3.7Z" +
        "M13.4 9.6c1.5-3.2 4.4-5.5 8.3-6.4-.1 3.8-1.9 7.2-5 8.8-1.1.6-2.2.8-3.3.7Z",
      fill: "#a9cdf7",
      stroke: "#0d1b2e",
      width: 1.2,
    },
    {
      d: "M12 8.4c1.6 0 2.4 1.3 2.4 3l-.8 4.6h-3.2l-.8-4.6c0-1.7.8-3 2.4-3Z",
      fill: "#7fb2ee",
      stroke: "#0d1b2e",
      width: 1.1,
    },
    {
      d: "M9.3 15.6h5.4l-.5 3.4L12 21.3l-2.2-2.3-.5-3.4Z",
      fill: "#4f86d4",
      stroke: "#0d1b2e",
      width: 1.1,
    },
    {
      d: "M10.2 6.1a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0-3.6 0Z",
      fill: "#dbeafe",
      stroke: "#0d1b2e",
      width: 1,
    },
  ],
  // a gold question mark, outlined so it holds on a light map
  seal: [
    { d: "M8.7 8.9a3.4 3.4 0 1 1 5.3 2.8c-1.2.8-2 1.5-2 3v.4", stroke: "#1c1405", width: 5 },
    { d: "M9.6 18.9a2.4 2.4 0 1 0 4.8 0a2.4 2.4 0 1 0-4.8 0Z", fill: "#1c1405" },
    { d: "M8.7 8.9a3.4 3.4 0 1 1 5.3 2.8c-1.2.8-2 1.5-2 3v.4", stroke: "#f3cd62", width: 2.7 },
    { d: "M10.55 18.9a1.45 1.45 0 1 0 2.9 0a1.45 1.45 0 1 0-2.9 0Z", fill: "#f3cd62" },
  ],
  // a coral cube seen from above a corner, a spoked wheel on each of its three faces, as the
  // game's red hidden cube: the lit top palest, the far side darkest
  cube: [
    { d: "M12 2.5L20.5 7.2L12 11.9L3.5 7.2Z", fill: "#f4a08c" },
    { d: "M3.5 7.2L12 11.9V21.5L3.5 16.8Z", fill: "#d9624f" },
    { d: "M20.5 7.2L12 11.9V21.5L20.5 16.8Z", fill: "#a83a2f" },
    { d: FACES.map((f) => faceSpokes(...f, 0.3, 3)).join(""), stroke: CUBE_WHEEL, width: 0.7 },
    { d: FACES.map((f) => faceRing(...f, 0.32)).join(""), stroke: CUBE_WHEEL, width: 1 },
    { d: FACES.map((f) => faceRing(...f, 0.1)).join(""), fill: CUBE_WHEEL },
    { d: "M3.5 7.2L12 11.9L20.5 7.2M12 11.9V21.5", stroke: CUBE_INK, width: 0.9 },
    { d: "M12 2.5L20.5 7.2V16.8L12 21.5L3.5 16.8V7.2Z", stroke: CUBE_INK, width: 1.5 },
  ],
  // a yellow four-pointed star, a main quest, a lighter one inside it for the gem's face
  questMain: [
    { d: STAR, fill: "#f2b544", stroke: "#3a2a06", width: 1.2 },
    { d: STAR_FACE, fill: "#ffe29a" },
  ],
  // the same in green, a side quest
  questSide: [
    { d: STAR, fill: "#22c55e", stroke: "#06301c", width: 1.2 },
    { d: STAR_FACE, fill: "#8ef0b8" },
  ],
};

/** The drawing itself, for an SVG. */
export function iconLayers(name: MarkIconName): readonly IconLayer[] {
  return isResourceIcon(name) ? resourceLayers(name) : ICONS[name];
}

const sprites = new Map<string, HTMLCanvasElement | null>();

/**
 * The icon drawn into a bitmap `px` CSS pixels square at `ratio` device pixels to one, made once
 * and kept: the map draws hundreds of each with drawImage on every redraw. Null where there is
 * no 2D canvas to draw with.
 */
export function iconSprite(
  name: MarkIconName,
  px: number,
  ratio: number,
): HTMLCanvasElement | null {
  const key = `${name}@${px}@${ratio}`;
  const known = sprites.get(key);
  if (known !== undefined) return known;
  const side = Math.ceil(px * ratio);
  const canvas = document.createElement("canvas");
  canvas.width = side;
  canvas.height = side;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    sprites.set(key, null);
    return null;
  }
  ctx.scale(side / 24, side / 24);
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const layer of iconLayers(name)) {
    const path = new Path2D(layer.d);
    if (layer.fill) {
      ctx.fillStyle = layer.fill;
      ctx.fill(path);
    }
    if (layer.stroke) {
      ctx.strokeStyle = layer.stroke;
      ctx.lineWidth = layer.width ?? 1;
      ctx.stroke(path);
    }
  }
  sprites.set(key, canvas);
  return canvas;
}
