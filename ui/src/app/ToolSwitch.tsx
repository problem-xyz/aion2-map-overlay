import type { KeyboardEvent as ReactKeyboardEvent } from "react";

import { type MessageKey, useT } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";
import Sheen from "@/shared/ui/Sheen";

export type Tool = "map" | "timers" | "app";

const TOOLS: readonly { id: Exclude<Tool, "app">; label: MessageKey; icon: IconName }[] = [
  { id: "map", label: "app.tools.map", icon: "map" },
  { id: "timers", label: "app.tools.timers", icon: "clock" },
];

export function toolPanelId(tool: Tool): string {
  return `pn-tool-${tool}`;
}

export interface ToolSwitchProps {
  active: Tool;
  onSelect: (tool: Tool) => void;
  /** An update waits: the gear carries the badge, as the client marks new mail. */
  updateWaiting: boolean;
}

/**
 * The panel's two tools, as the client's selected tabs, and the gear that opens what both share.
 * The tabs are a tablist over the tool below; the gear is a third tab, since it swaps the same
 * area for the app's own settings.
 */
export default function ToolSwitch({ active, onSelect, updateWaiting }: ToolSwitchProps) {
  const t = useT();
  const all: Tool[] = ["map", "timers", "app"];

  const onKey = (e: ReactKeyboardEvent, tool: Tool) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const next = all[(all.indexOf(tool) + step + all.length) % all.length] ?? "map";
    onSelect(next);
    document.getElementById(`pn-tool-tab-${next}`)?.focus();
  };

  const tab = (tool: Tool) => ({
    id: `pn-tool-tab-${tool}`,
    type: "button" as const,
    role: "tab",
    "aria-selected": tool === active,
    "aria-controls": toolPanelId(tool),
    tabIndex: tool === active ? 0 : -1,
    onClick: () => onSelect(tool),
    onKeyDown: (e: ReactKeyboardEvent) => onKey(e, tool),
  });

  return (
    <div role="tablist" aria-label={t("app.tools.label")} className="pn-tools">
      {TOOLS.map(({ id, label, icon }) => (
        <button key={id} {...tab(id)} className={id === active ? "pn-tool on" : "pn-tool"}>
          {id === active ? <Sheen /> : null}
          <Icon name={icon} className="pn-tool-icon" />
          <span>{t(label)}</span>
        </button>
      ))}
      <button
        {...tab("app")}
        className={active === "app" ? "pn-tool pn-tool-gear on" : "pn-tool pn-tool-gear"}
        aria-label={t("app.tools.settings")}
        title={t("app.tools.settings")}
      >
        {active === "app" ? <Sheen /> : null}
        <Icon name="gear" className="pn-tool-icon" />
        {updateWaiting ? (
          <span className="pn-tile-badge" title={t("panel.menu.update")}>
            <span className="pn-sr-only">{t("panel.menu.update")}</span>
          </span>
        ) : null}
      </button>
    </div>
  );
}
