import type { MarkerIcon } from "@/shared/backend/contract";
import type { MessageKey } from "@/shared/i18n";

/**
 * A route marker's colour: the value for CSS and the key of its name — nothing else labels the
 * swatch in the palette. The name is a key rather than a string because this module is not a
 * component and cannot call `useT`; `ColorPicker` translates it where it draws the swatch.
 */
export interface MarkerColor {
  value: string;
  nameKey: MessageKey;
}

// Route marker colours. All of them are light: the number on the swatch is drawn dark and has to
// stay readable. The first four are the interface palette, the rest are taken from the map's
// object categories, so that a manual pick and a colour inherited from an object land in one set.
export const MARKER_COLORS: readonly MarkerColor[] = [
  { value: "#f2b544", nameKey: "editor.colors.amber" }, // the route's default colour
  { value: "#4fd1c5", nameKey: "editor.colors.teal" }, // the end of the route
  { value: "#f07178", nameKey: "editor.colors.red" },
  { value: "#6ea8ff", nameKey: "editor.colors.blue" },
  { value: "#a78bfa", nameKey: "editor.colors.purple" },
  { value: "#22c55e", nameKey: "editor.colors.green" },
  { value: "#38bdf8", nameKey: "editor.colors.sky" },
  { value: "#e7eaf1", nameKey: "editor.colors.white" },
];

/**
 * The colour a quest icon gives its point: yellow for a main quest, green for a side one, as the
 * game marks them. Picking the icon picks the colour with it; the colour can be changed after.
 */
export const QUEST_COLOR: Record<MarkerIcon, string> = {
  main: MARKER_COLORS[0]?.value ?? "#f2b544", // amber
  side: MARKER_COLORS.find((c) => c.nameKey === "editor.colors.green")?.value ?? "#22c55e",
};

/** The colour for key number 1–8. null — there is no such key in the palette. */
export function colorByIndex(index: number): string | null {
  return MARKER_COLORS[index]?.value ?? null;
}
