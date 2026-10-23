/**
 * Which page the address asks for.
 *
 * One build serves every window, and the only thing that tells them apart is the hash:
 * `index.html` is the control panel, `#editor` the route editor, `#steps` and `#timers` the
 * plaques over the game, `#timeline` the day timeline, `#pets-map` the pets' map (see the windows
 * in `qt/`).
 */

import type { ComponentType } from "react";

import ControlPage from "@/app/ControlPage";
import EditorPage from "@/features/editor/EditorPage";
import PetsMapPage from "@/features/pets/map/PetsMapPage";
import StepsPage from "@/features/steps/StepsPage";
import TimersPlaquePage from "@/features/timers/plaque/TimersPlaquePage";
import TimelinePage from "@/features/timers/timeline/TimelinePage";

export type PageId = "" | "editor" | "steps" | "timers" | "timeline" | "pets-map";

export const PAGES: Record<PageId, ComponentType> = {
  "": ControlPage,
  editor: EditorPage,
  steps: StepsPage,
  timers: TimersPlaquePage,
  timeline: TimelinePage,
  "pets-map": PetsMapPage,
};

export function pageFromHash(hash: string): PageId {
  if (hash.startsWith("#editor")) return "editor";
  if (hash.startsWith("#steps")) return "steps";
  if (hash.startsWith("#timers")) return "timers";
  if (hash.startsWith("#timeline")) return "timeline";
  if (hash.startsWith("#pets-map")) return "pets-map";
  return "";
}
