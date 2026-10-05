/**
 * Which of the three pages the address asks for.
 *
 * One build serves three windows, and the only thing that tells them apart is the hash:
 * `index.html` is the control panel, `index.html#editor` the route editor, `index.html#steps`
 * the plaque over the game (see `qt/editor_window.py` and `qt/steps_window.py`).
 */

import type { ComponentType } from "react";

import ControlPage from "@/app/ControlPage";
import EditorPage from "@/features/editor/EditorPage";
import StepsPage from "@/features/steps/StepsPage";
import TimersPlaquePage from "@/features/timers/plaque/TimersPlaquePage";

export type PageId = "" | "editor" | "steps" | "timers";

export const PAGES: Record<PageId, ComponentType> = {
  "": ControlPage,
  editor: EditorPage,
  steps: StepsPage,
  timers: TimersPlaquePage,
};

export function pageFromHash(hash: string): PageId {
  if (hash.startsWith("#editor")) return "editor";
  if (hash.startsWith("#steps")) return "steps";
  if (hash.startsWith("#timers")) return "timers";
  return "";
}
