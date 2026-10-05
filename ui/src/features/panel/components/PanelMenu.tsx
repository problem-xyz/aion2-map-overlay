import { type KeyboardEvent as ReactKeyboardEvent, useEffect } from "react";

import { useLatest } from "@/shared/hooks/useLatest";
import { type MessageKey, useT } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";
import Sheen from "@/shared/ui/Sheen";

export type PanelSection = "routes" | "progress" | "settings";

interface Tile {
  id: PanelSection;
  label: MessageKey;
  icon: IconName;
  /** A physical key (KeyboardEvent.code), so the shortcut works on any keyboard layout. */
  code: string;
  cap: string;
}

const TILES: readonly Tile[] = [
  { id: "routes", label: "panel.menu.routes", icon: "route", code: "KeyR", cap: "R" },
  { id: "progress", label: "panel.menu.progress", icon: "flag", code: "KeyP", cap: "P" },
  { id: "settings", label: "panel.menu.settings", icon: "gear", code: "KeyS", cap: "S" },
];

const EDITOR_CODE = "KeyE";

export function sectionPanelId(id: PanelSection): string {
  return `pn-section-${id}`;
}

function inField(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
}

export interface PanelMenuProps {
  active: PanelSection;
  onSelect: (id: PanelSection) => void;
  onEditor: () => void;
}

/**
 * The sections of the panel, as tiles like the client's main menu, each with its key in the
 * corner. The panel used to be one long column the player scrolled through to reach Settings;
 * now a section is one press away. The tiles are a tablist over the section below.
 *
 * Three, where there were six: what belongs together is together -- the progress along a route
 * with the plaque that lists its points, the routes with the editor that draws them, the map
 * area with the rest of the settings. E still opens the editor from anywhere in the panel; its
 * button now sits over the routes.
 */
export default function PanelMenu({ active, onSelect, onEditor }: PanelMenuProps) {
  const t = useT();
  const live = useLatest({ onSelect, onEditor });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || inField(e.target)) return;
      if (e.code === EDITOR_CODE) {
        e.preventDefault();
        live.current.onEditor();
        return;
      }
      const tile = TILES.find((x) => x.code === e.code);
      if (tile) {
        e.preventDefault();
        live.current.onSelect(tile.id);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [live]);

  // Arrow keys move between the tabs, as a tablist is expected to
  const onTabKey = (e: ReactKeyboardEvent, index: number) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = TILES[(index + step + TILES.length) % TILES.length];
    if (next) {
      onSelect(next.id);
      document.getElementById(`pn-tab-${next.id}`)?.focus();
    }
  };

  return (
    <nav className="pn-menu">
      <div role="tablist" aria-label={t("panel.menu.label")} className="pn-menu-tabs">
        {TILES.map((tile, i) => {
          const on = tile.id === active;
          return (
            <button
              key={tile.id}
              id={`pn-tab-${tile.id}`}
              type="button"
              role="tab"
              aria-selected={on}
              aria-controls={sectionPanelId(tile.id)}
              aria-keyshortcuts={tile.cap}
              tabIndex={on ? 0 : -1}
              className={on ? "pn-tile on" : "pn-tile"}
              onClick={() => onSelect(tile.id)}
              onKeyDown={(e) => onTabKey(e, i)}
            >
              {on ? <Sheen /> : null}
              <kbd className="ui-kbd pn-tile-key" aria-hidden="true">
                {tile.cap}
              </kbd>
              <Icon name={tile.icon} className="pn-tile-icon" />
              <span className="pn-tile-label">{t(tile.label)}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
