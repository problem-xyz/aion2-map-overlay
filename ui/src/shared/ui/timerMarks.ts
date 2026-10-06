/**
 * The timers' marks: one filled drawing per kind of event, after the client's own icons in shape
 * and colour and drawn here, as the map's marks are (markIcons.ts). A horned red head for every
 * boss, the lavender vortex of the Spacetime Rift, a fox for the Shugo Festival, a keep under
 * its crystal for the Artifact Siege, and the two resets.
 *
 * Each sits on a disc of its kind's hue, which is data rather than interface colour -- taken from
 * the route markers' palette -- so a row, a lane of the day strip and the plaque all say which kind
 * of thing they are in the same colour.
 */

import type { IconLayer } from "./markIcons";

export type TimerIconName = "demon" | "vortex" | "fox" | "siege" | "daily" | "weekly";

/** A circle as a path, for a layer list that only draws paths. */
function circle(cx: number, cy: number, r: number): string {
  return `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z`;
}

/** The vortex's six blades: each curls from the hub out to a point a sixth of a turn round. */
function blades(): string {
  const at = (r: number, deg: number) => {
    const a = (deg * Math.PI) / 180;
    return `${(12 + r * Math.cos(a)).toFixed(2)} ${(12 + r * Math.sin(a)).toFixed(2)}`;
  };
  let d = "";
  for (let k = 0; k < 6; k += 1) {
    const a = k * 60;
    d += `M${at(4, a)}Q${at(9.6, a + 8)} ${at(10.9, a + 58)}Q${at(7, a + 46)} ${at(5.2, a + 66)}Z`;
  }
  return d;
}

const RED_INK = "#1a0a0c";
const FOX_INK = "#2b1a1e";
const STONE_INK = "#102a3c";
const PAPER_INK = "#1d232c";

// Three quarters of a circle round the centre, clockwise from the right to the top left: the
// daily reset's arrow, stroked twice, dark under light, for an outline that holds over the game.
const DAILY_ARC = "M18.77 9.54A7.2 7.2 0 1 1 8.4 5.76";
const VORTEX_INK = "#15171c";

const ICONS: Record<TimerIconName, readonly IconLayer[]> = {
  // a red head between two horns swept up to the corners, yellow eyes, two fangs: drawn for 22px,
  // where finer detail turned to mush
  demon: [
    {
      d:
        "M8.4 12C3.8 11.6.6 7.6 1.6 1.8c2 3.2 5 4.6 7.8 4.8 1.2.1 2 .6 2.2 1.8Z" +
        "M15.6 12c4.6-.4 7.8-4.4 6.8-10.2-2 3.2-5 4.6-7.8 4.8-1.2.1-2 .6-2.2 1.8Z",
      fill: "#a8262f",
      stroke: RED_INK,
      width: 1.2,
    },
    {
      d: "M12 6c4.4 0 7 2.8 6.8 6.6-.2 3.6-2.8 7.2-6.8 10-4-2.8-6.6-6.4-6.8-10C5 8.8 7.6 6 12 6Z",
      fill: "#e0353e",
      stroke: RED_INK,
      width: 1.2,
    },
    {
      d: "M6.6 10.2l4.8 2-.4 2.6-4.1-1.4ZM17.4 10.2l-4.8 2 .4 2.6 4.1-1.4Z",
      fill: "#ffd54a",
      stroke: RED_INK,
      width: 0.8,
    },
    { d: "M8 16.4c1.2 1 6.8 1 8 0l-.6 2H8.6Z", fill: RED_INK },
    {
      d: "M8.9 17.1l1.3 3.7 1.2-3.4ZM12.6 17.4l1.2 3.4 1.3-3.7Z",
      fill: "#fff6e8",
      stroke: RED_INK,
      width: 0.5,
    },
  ],
  // the rift: six lavender blades curling round a dark eye
  vortex: [
    { d: blades(), fill: "#c3b2ff", stroke: VORTEX_INK, width: 1 },
    { d: circle(12, 12, 4.3), fill: "#a48cf0", stroke: VORTEX_INK, width: 1 },
    { d: circle(12, 12, 1.9), fill: VORTEX_INK },
    { d: "M9.4 10.6a3 3 0 0 1 3.2-1.7", stroke: "#efe9ff", width: 0.8 },
  ],
  // a fox's face, ears tipped dark, the lower half cream, eyes closed in a smile
  fox: [
    {
      d: "M4.2 11l.4-8.6 5.8 5.2ZM19.8 11l-.4-8.6-5.8 5.2Z",
      fill: "#f8822e",
      stroke: FOX_INK,
      width: 0.9,
    },
    { d: "M4.55 3.1l.2 2.5 2.35-.4ZM19.45 3.1l-.2 2.5-2.35-.4Z", fill: FOX_INK },
    { d: "M5.6 9.6l.2-4.2 2.8 2.5ZM18.4 9.6l-.2-4.2-2.8 2.5Z", fill: "#d94a2a" },
    {
      d: "M12 6.4c4.2 0 8.2 2.4 8.6 6.8.3 4.4-3.6 8.2-8.6 8.2s-8.9-3.8-8.6-8.2C3.8 8.8 7.8 6.4 12 6.4Z",
      fill: "#f8822e",
      stroke: FOX_INK,
      width: 0.9,
    },
    {
      d: "M3.6 13.4c2.4-.8 5 0 7 1.5.7.5 2.1.5 2.8 0 2-1.5 4.6-2.3 7-1.5.1 4.4-3.6 8-8.4 8s-8.5-3.6-8.4-8Z",
      fill: "#fbe0bf",
    },
    { d: "M9 8.6c1-.6 2-.9 3-.9s2 .3 3 .9", stroke: "#ffc48a", width: 0.8 },
    { d: "M7.3 12.1c.6-1 1.8-1 2.4 0M14.3 12.1c.6-1 1.8-1 2.4 0", stroke: FOX_INK, width: 1.1 },
    { d: `${circle(7.4, 15.2, 1.1)}${circle(16.6, 15.2, 1.1)}`, fill: "#f7a990" },
    { d: "M10.7 15.3h2.6c0 1-.6 1.6-1.3 1.6s-1.3-.6-1.3-1.6Z", fill: FOX_INK },
    {
      d: "M12 16.9v.8M10.3 18.6c.7 0 1.3-.4 1.7-.9.4.5 1 .9 1.7.9",
      stroke: FOX_INK,
      width: 0.8,
    },
  ],
  // a stone keep with battlements and a dark gate, the artifact's crystal over it
  siege: [
    { d: "M12 1.6l3 4.8-3 4.2-3-4.2Z", fill: "#8ad8ff", stroke: STONE_INK, width: 0.9 },
    { d: "M12 2.8l1.8 3.6L12 9.2Z", fill: "#e6f7ff" },
    {
      d: "M3.4 22.4V10.2h2.8V7.6H9v2.6h1.6V7.6h2.8v2.6H15V7.6h2.8v2.6h2.8v12.2Z",
      fill: "#7593b8",
      stroke: STONE_INK,
      width: 1.1,
    },
    { d: "M3.4 13.6h17.2", stroke: "#3e5a78", width: 0.7 },
    { d: "M9.4 22.4v-5.2c0-1.6 1.1-2.6 2.6-2.6s2.6 1 2.6 2.6v5.2Z", fill: STONE_INK },
    { d: "M6.4 16.2h1.5v2.4H6.4ZM16.1 16.2h1.5v2.4h-1.5Z", fill: "#23405a" },
  ],
  // the daily reset: an arrow coming round a sun, drawn as a stroke with a broad head so it
  // still reads as one at 20 px, where the earlier filled ring with a small head read as a "C"
  daily: [
    { d: DAILY_ARC, stroke: PAPER_INK, width: 4.8 },
    { d: "M12.56 3.36L5.84 2.53L9.92 9.6Z", fill: "#d4d9e0", stroke: PAPER_INK, width: 0.9 },
    { d: DAILY_ARC, stroke: "#d4d9e0", width: 3.2 },
    { d: circle(12, 12, 3), fill: "#f8c13a", stroke: PAPER_INK, width: 0.9 },
  ],
  // the weekly reset: a calendar page, its red header and the week's last day marked
  weekly: [
    { d: "M3 5.6h18v15.8H3Z", fill: "#d4d9e0", stroke: PAPER_INK, width: 1 },
    { d: "M3 5.6h18V10H3Z", fill: "#e0353e", stroke: PAPER_INK, width: 1 },
    { d: "M7.2 2.6v4.8M16.8 2.6v4.8", stroke: PAPER_INK, width: 1.8 },
    {
      d: "M5.4 12.6h3V15h-3ZM10.5 12.6h3V15h-3ZM15.6 12.6h3V15h-3ZM5.4 16.6h3V19h-3ZM10.5 16.6h3V19h-3Z",
      fill: "#9aa2ad",
    },
    { d: "M15.6 16.6h3V19h-3Z", fill: "#e8343e" },
  ],
};

/**
 * The hue of each kind, from the route markers' palette (editor/lib/palette.ts): the Rift's
 * lavender, the festival's amber, the Abyss's blue for the siege, red for every boss, and a
 * neutral silver for the resets, which are housekeeping rather than something to attend.
 */
const HUES: Record<TimerIconName, string> = {
  demon: "#f07178",
  vortex: "#a78bfa",
  fox: "#f2b544",
  siege: "#6ea8ff",
  daily: "#c2c8d0",
  weekly: "#c2c8d0",
};

/** The hue the Abyss and world groups are headed in, on the plaque and in the filters. */
export const REALM_HUES = { abyss: "#6ea8ff", world: "#22c55e" } as const;

export function isTimerIcon(name: string): name is TimerIconName {
  return name in ICONS;
}

// For an icon a newer schedule names and this build does not draw yet: a plain silver token,
// which claims no kind it may not be
const UNKNOWN: readonly IconLayer[] = [
  { d: circle(12, 12, 7), fill: "#d4d9e0", stroke: PAPER_INK, width: 1 },
  { d: circle(12, 12, 2.4), fill: PAPER_INK },
];

/** The drawing, or a neutral token for a name the data has and this build does not draw. */
export function timerLayers(name: string): readonly IconLayer[] {
  return isTimerIcon(name) ? ICONS[name] : UNKNOWN;
}

export function timerHue(name: string): string {
  return isTimerIcon(name) ? HUES[name] : HUES.daily;
}
