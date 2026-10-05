import { useCallback, useState } from "react";

import AppSettings from "@/features/panel/AppSettings";
import SupportBlock from "@/features/panel/components/SupportBlock";
import UpdateBanner from "@/features/panel/components/UpdateBanner";
import PanelPage from "@/features/panel/PanelPage";
import TimersPage from "@/features/timers/TimersPage";
import { useBackendSignal, useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, NotifyPayload } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useT } from "@/shared/i18n";
import { useToasts } from "@/shared/ui/ToastProvider";
import Toasts from "@/shared/ui/Toasts";

import ToolSwitch, { type Tool, toolPanelId } from "./ToolSwitch";

const TOOL_KEY = "mo.panel.tool";
const TOOLS: readonly Tool[] = ["map", "timers", "app"];

function loadTool(): Tool {
  try {
    const stored = window.localStorage.getItem(TOOL_KEY) ?? "";
    return TOOLS.find((x) => x === stored) ?? "map";
  } catch {
    return "map";
  }
}

/**
 * The control panel: the switch between its two tools, the map and the timers, and what both
 * share -- the update banner over them, the app's own settings behind the gear, the support links
 * and the toasts. Each tool is a feature of its own; this page is where they meet, since a feature
 * does not import another.
 */
export default function ControlPage() {
  const api = useApi();
  const t = useT();
  const toasts = useToasts();
  const state = useBackendState<AppState, AppState | null>((s) => s);
  const [tool, setToolState] = useState<Tool>(loadTool);

  const setTool = useCallback((next: Tool) => {
    setToolState(next);
    try {
      window.localStorage.setItem(TOOL_KEY, next);
    } catch {
      /* private mode, or writes are forbidden -- the panel opens on the map next time */
    }
  }, []);

  useBackendSignal<NotifyPayload>("notify", (payload) => toasts.push(payload), { parse: true });

  if (!state || !api) return null;
  const updateWaiting = state.update?.phase === "available" || state.update?.phase === "ready";

  return (
    <div className="app pn-app">
      <UpdateBanner
        update={state.update}
        repoUrl={state.repoUrl}
        editorOpen={state.editorOpen}
        onDownload={() => api.downloadUpdate()}
        onRestart={() => api.installUpdate(true)}
        onSkip={(version) => api.skipUpdate(version)}
        onOpenUrl={(url) => api.openUrl(url)}
      />

      <ToolSwitch active={tool} onSelect={setTool} updateWaiting={updateWaiting} />

      <div
        id={toolPanelId(tool)}
        role="tabpanel"
        aria-labelledby={`pn-tool-tab-${tool}`}
        className="pn-tool-panel"
      >
        {tool === "map" ? <PanelPage /> : tool === "timers" ? <TimersPage /> : <AppSettings />}
      </div>

      <SupportBlock
        links={state.links}
        repoUrl={state.repoUrl}
        banner={state.banner}
        onOpenUrl={(url) => api.openUrl(url)}
        onCopy={(text) => api.copyText(text)}
      />

      <footer className="foot">
        <span>Aion 2 - Map Overlay {state.version}</span>
        <span>
          {state.captureBackend ? t("panel.footer.capture", { backend: state.captureBackend }) : ""}
        </span>
      </footer>

      <Toasts />
    </div>
  );
}
