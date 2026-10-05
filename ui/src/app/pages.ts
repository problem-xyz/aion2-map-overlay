/**
 * Which page the address asks for.
 *
 * One build serves every window, and the only thing that tells them apart is the hash:
 * `index.html` is the control panel, `#editor` the route editor, `#steps` and `#timers` the
 * plaques over the game, `#timeline` the day timeline (see the windows in `qt/`).
 */

import type { ComponentType } from "react";

import ControlPage from "@/app/ControlPage";
import EditorPage from "@/features/editor/EditorPage";
import StepsPage from "@/features/steps/StepsPage";
import TimersPlaquePage from "@/features/timers/plaque/TimersPlaquePage";
import TimelinePage from "@/features/timers/timeline/TimelinePage";

export type PageId = "" | "editor" | "steps" | "timers" | "timeline";

export const PAGES: Record<PageId, ComponentType> = {
  "": ControlPage,
  editor: EditorPage,
  steps: StepsPage,
  timers: TimersPlaquePage,
  timeline: TimelinePage,
};

export function pageFromHash(hash: string): PageId {
  if (hash.startsWith("#editor")) return "editor";
  if (hash.startsWith("#steps")) return "steps";
  if (hash.startsWith("#timers")) return "timers";
  if (hash.startsWith("#timeline")) return "timeline";
  return "";
}
