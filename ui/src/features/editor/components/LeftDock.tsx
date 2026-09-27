import { useState } from "react";

import { useT } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";

import { useEditorState } from "../EditorContext";

import ObjectsPanel from "./ObjectsPanel";
import PointsPanel from "./PointsPanel";
import RouteViewPanel from "./RouteViewPanel";

type Pane = "points" | "objects" | "view";

const PANE_KEY = "mo.editor.pane";

function loadPane(): Pane | null {
  try {
    const stored = window.localStorage.getItem(PANE_KEY);
    if (stored === "none") return null;
    return stored === "objects" || stored === "view" ? stored : "points";
  } catch {
    return "points";
  }
}

function savePane(pane: Pane | null): void {
  try {
    window.localStorage.setItem(PANE_KEY, pane ?? "none");
  } catch {
    /* private mode, or writes are forbidden -- it opens on the points next time */
  }
}

/**
 * The left edge of the editor: a rail of icons, as the client keeps its own down one side, and
 * the drawer the selected icon opens. The route's points and the map's objects share the one
 * drawer, so the map keeps the rest of the window; pressing the open icon again folds it away.
 */
export default function LeftDock() {
  const t = useT();
  const { markers, objects } = useEditorState();
  const [pane, setPane] = useState<Pane | null>(loadPane);

  const toggle = (next: Pane) => {
    const value = pane === next ? null : next;
    setPane(value);
    savePane(value);
  };

  // The view has no count: it is settings, not a list of anything
  const rail: { id: Pane; icon: IconName; label: string; count: number | null }[] = [
    { id: "points", icon: "list", label: t("editor.markers.title"), count: markers.length },
    {
      id: "objects",
      icon: "layers",
      label: t("editor.objects.title"),
      // from the index, not the sets: it leaves out the categories the editor does not show
      count: objects ? objects.points.length : 0,
    },
    { id: "view", icon: "gear", label: t("editor.view.title"), count: null },
  ];
  const open = rail.find((r) => r.id === pane);

  return (
    <div className="ed-dock">
      <nav className="ui-frame ed-rail" aria-label={t("editor.dock.label")}>
        {rail.map((item) => (
          <button
            key={item.id}
            type="button"
            className={pane === item.id ? "ed-rail-btn on" : "ed-rail-btn"}
            aria-pressed={pane === item.id}
            aria-controls={`ed-pane-${item.id}`}
            title={item.label}
            onClick={() => toggle(item.id)}
          >
            <Icon name={item.icon} />
            <span className="ui-sr-only">{item.label}</span>
          </button>
        ))}
      </nav>

      {pane ? (
        <section
          id={`ed-pane-${pane}`}
          className="ui-frame ed-drawer"
          aria-labelledby={`ed-pane-${pane}-title`}
        >
          <h2 id={`ed-pane-${pane}-title`} className="ui-title">
            {open?.label}
            {open && open.count !== null ? (
              <span className="ed-drawer-count">{open.count}</span>
            ) : null}
          </h2>
          {pane === "points" ? <PointsPanel /> : null}
          {pane === "objects" ? <ObjectsPanel /> : null}
          {pane === "view" ? <RouteViewPanel /> : null}
        </section>
      ) : null}
    </div>
  );
}
