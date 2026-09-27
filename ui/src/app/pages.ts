/**
 * Which of the three pages the address asks for.
 *
 * One build serves three windows, and the only thing that tells them apart is the hash:
 * `index.html` is the control panel, `index.html#editor` the route editor, `index.html#steps`
 * the plaque over the game (see `qt/editor_window.py` and `qt/steps_window.py`).
 */

import type { ComponentType } from "react";

import EditorPage from "@/features/editor/EditorPage";
import PanelPage from "@/features/panel/PanelPage";
import StepsPage from "@/features/steps/StepsPage";

export type PageId = "" | "editor" | "steps";

export const PAGES: Record<PageId, ComponentType> = {
  "": PanelPage,
  editor: EditorPage,
  steps: StepsPage,
};

export function pageFromHash(hash: string): PageId {
  if (hash.startsWith("#editor")) return "editor";
  if (hash.startsWith("#steps")) return "steps";
  return "";
}
