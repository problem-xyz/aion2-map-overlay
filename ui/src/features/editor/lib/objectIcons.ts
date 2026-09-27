/**
 * The colour each object category with an icon of its own takes. Which categories have one is
 * in shared/ui/objectMarks, the drawings in shared/ui/markIcons, where the panel and the steps
 * plaque can reach them too. Every other category is a coloured dot.
 */

import type { MessageKey } from "@/shared/i18n";
import type { ObjectIconName } from "@/shared/ui/markIcons";
import { iconFor } from "@/shared/ui/objectMarks";

import { MARKER_COLORS } from "./palette";

export type { ObjectIconName };
// Which category has which icon is shared: the panel's list of points draws them too
export { iconFor };

/**
 * The palette colour an icon's category takes, as the owner set them out: teleports purple,
 * hidden cubes red, Empyrean Traces white, seals blue -- with quests yellow and green, the six
 * colours a route is read by. A point dropped on a teleport turns purple, its leg of the route
 * with it, and the colour picker shows that swatch pressed.
 */
const ICON_COLOR: Record<ObjectIconName, MessageKey> = {
  trace: "editor.colors.white",
  teleport: "editor.colors.purple",
  // purple too: the colour says what the point is, a teleport; the winged figure says whose
  teleportElyos: "editor.colors.purple",
  // blue, where the icon is gold: amber is a main quest's colour, and the route's own
  seal: "editor.colors.blue",
  cube: "editor.colors.red",
};

/** The colour of a category drawn with this icon. */
export function iconColor(name: ObjectIconName): string {
  const swatch = MARKER_COLORS.find((c) => c.nameKey === ICON_COLOR[name]);
  // every key above is one of the palette's
  return swatch ? swatch.value : "#e7eaf1";
}
