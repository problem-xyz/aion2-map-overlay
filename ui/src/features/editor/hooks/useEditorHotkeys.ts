/**
 * The listener is attached once and reads the current actions through a ref: rebuilding it on
 * every edit would mean removing and re-adding the handler ten times during a single drag.
 */

import { useEffect } from "react";

import { useLatest } from "@/shared/hooks/useLatest";

import type { EditorActions } from "../EditorContext";
import { colorByIndex } from "../lib/palette";
import type { EditorMarker } from "../lib/routeDoc";

/** Inside an input, the keys belong to the field and not to the editor -- all but Ctrl+S. */
export function isField(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName);
}

export function useEditorHotkeys(
  actions: EditorActions,
  selectedId: number | null,
  markers: readonly EditorMarker[] = [],
) {
  const latest = useLatest({ actions, selectedId, markers });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const { actions: a, selectedId: selected, markers: route } = latest.current;
      const field = isField(e.target);

      if (e.key === "Escape") {
        a.select(null);
        if (field) (e.target as HTMLElement).blur();
        return;
      }

      const ctrl = e.ctrlKey || e.metaKey;
      const key = e.key.toLowerCase();

      // A field has no use of its own for Ctrl+S, and finishing a label is exactly when it gets
      // pressed. Undo, redo and the single keys stay the field's.
      if (ctrl && key === "s") {
        e.preventDefault();
        void a.save();
        return;
      }
      if (field) return;

      if (ctrl && key === "z" && !e.shiftKey) {
        e.preventDefault();
        a.undo();
      } else if (ctrl && (key === "y" || (key === "z" && e.shiftKey))) {
        e.preventDefault();
        a.redo();
      } else if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown") && selected !== null) {
        // Alt+Up/Down moves the selected point one place along the route
        e.preventDefault();
        const at = route.findIndex((m) => m.id === selected);
        if (at >= 0) a.moveMarkerTo(selected, at + (e.key === "ArrowUp" ? -1 : 1));
      } else if ((e.key === "Delete" || e.key === "Backspace") && selected !== null) {
        e.preventDefault();
        a.deleteMarker(selected);
      } else if (selected !== null && /^[1-9]$/.test(e.key)) {
        e.preventDefault(); // 1-8 pick a marker colour, 9 gives the route colour back
        a.setColor(selected, colorByIndex(Number(e.key) - 1));
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [latest]);
}
