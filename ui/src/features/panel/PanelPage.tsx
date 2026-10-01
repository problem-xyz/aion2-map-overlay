import { useCallback, useState, type ReactNode } from "react";

import { useBackendSignal, useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, NotifyPayload, ProgressState } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { useT } from "@/shared/i18n";
import { useToasts } from "@/shared/ui/ToastProvider";
import Toasts from "@/shared/ui/Toasts";

import AutoMarkBlock from "./components/AutoMarkBlock";
import FirstRun from "./components/FirstRun";
import HeroCard from "./components/HeroCard";
import OverlayFilters from "./components/OverlayFilters";
import PanelMenu, { type PanelSection, sectionPanelId } from "./components/PanelMenu";
import PreviewBlock from "./components/PreviewBlock";
import ProgressBlock from "./components/ProgressBlock";
import Region from "./components/Region";
import RoutesList from "./components/RoutesList";
import RunRow from "./components/RunRow";
import SearchHint from "./components/SearchHint";
import SettingsBlock from "./components/SettingsBlock";
import Status from "./components/Status";
import StepsBlock from "./components/StepsBlock";
import SupportBlock from "./components/SupportBlock";
import UpdateBanner from "./components/UpdateBanner";
import UpdatesBlock from "./components/UpdatesBlock";
import WarmUp from "./components/WarmUp";
import { usePointIcons } from "./hooks/usePointIcons";

const SECTION_KEY = "mo.panel.section";
const SECTIONS: readonly PanelSection[] = ["routes", "progress", "settings"];
// The sections that were folded into another: a panel last left on one opens on its new home
const FOLDED: Readonly<Record<string, PanelSection>> = { steps: "progress", area: "settings" };
const NO_PROGRESS: ProgressState = { done: 0, total: 0, map: null, markers: [] };

function loadSection(): PanelSection {
  try {
    const stored = window.localStorage.getItem(SECTION_KEY) ?? "";
    return SECTIONS.find((s) => s === stored) ?? FOLDED[stored] ?? "routes";
  } catch {
    return "routes";
  }
}

/**
 * The control panel.
 *
 * It holds no copy of the backend state: every field is read through a selector, so a stats
 * tick at 10 Hz re-renders the status strip and nothing else. What it does own is the two
 * pieces of state the backend has no opinion about -- whether the preview is switched on, and
 * the toast queue.
 */
export default function PanelPage() {
  const api = useApi();
  const t = useT();
  const confirm = useConfirm();
  const changeSetting = useSettingsPatch();
  const toasts = useToasts();
  const [previewOn, setPreviewOn] = useState(false);
  const [section, setSectionState] = useState<PanelSection>(loadSection);

  const setSection = useCallback((next: PanelSection) => {
    setSectionState(next);
    try {
      window.localStorage.setItem(SECTION_KEY, next);
    } catch {
      /* private mode, or writes are forbidden -- the panel opens on Routes next time */
    }
  }, []);

  useBackendSignal<NotifyPayload>("notify", (payload) => toasts.push(payload), { parse: true });

  const state = useBackendState<AppState, AppState | null>((s) => s);

  const togglePreview = useCallback(
    (on: boolean) => {
      setPreviewOn(on);
      api?.setPreview(on);
    },
    [api],
  );

  const route = state?.routes.find((r) => r.id === state.route);
  const pointIcons = usePointIcons(route?.map, state?.progress ?? NO_PROGRESS);

  if (!state || !api) return null;

  const updateWaiting = state.update?.phase === "available" || state.update?.phase === "ready";
  const panel = (id: PanelSection) => ({
    id: sectionPanelId(id),
    role: "tabpanel",
    "aria-labelledby": `pn-tab-${id}`,
    className: "pn-section",
  });

  // Each section's content, built once: shown in its tab panel, and drawn unseen by WarmUp
  const content: Record<PanelSection, ReactNode> = {
    routes: (
      <>
        <RoutesList
          routes={state.routes}
          active={state.route}
          onSelect={(id) => api.setRoute(id)}
          onEditor={() => api.openEditor(state.route ?? "")}
          onNew={() => api.openEditor("")}
          onEdit={(id) => api.openEditor(id)}
          onDelete={(r) => {
            void confirm(t("panel.routes.confirmDelete", { label: r.label }), {
              confirmLabel: t("panel.routes.deleteTip"),
              danger: true,
            }).then((ok) => {
              if (ok) api.deleteRoute(r.id);
            });
          }}
          onReorder={(ids) => api.reorderRoutes(ids)}
          onImport={() => api.importRouteFile()}
          onPaste={() => api.pasteRouteCode()}
          onOpenFolder={() => api.openRoutesFolder()}
        />
      </>
    ),
    // The short card first: under the list of points, however long, it went unseen
    progress: (
      <>
        <AutoMarkBlock
          auto={state.settings.auto_progress}
          radius={state.settings.arrive_radius}
          map={state.progress.map}
          schema={state.settingsSchema}
          onToggle={(on) => changeSetting("auto_progress", on)}
          onRadius={(v) => changeSetting("arrive_radius", v)}
        />
        <ProgressBlock
          progress={state.progress}
          icons={pointIcons}
          onSet={(n) => api.setProgress(n)}
          onReset={() => api.resetProgress()}
        />
      </>
    ),
    settings: (
      <>
        <Region
          region={state.region}
          onSelect={() => api.selectRegion()}
          onReset={() => api.resetRegion()}
        >
          <PreviewBlock
            enabled={previewOn}
            running={state.running}
            showAnchor={state.settings.auto_progress}
            onToggle={togglePreview}
            onAnchor={(fx, fy) => api.setPlayerAnchor(fx, fy)}
          />
        </Region>
        <SettingsBlock
          settings={state.settings}
          schema={state.settingsSchema}
          onChange={changeSetting}
          checklist={
            <StepsBlock
              pinned={state.steps.pinned}
              scale={state.settings.steps_scale}
              schema={state.settingsSchema}
              onPin={(on) => api.setStepsPinned(on)}
              onScale={(v) => changeSetting("steps_scale", v)}
            />
          }
          onReset={() => {
            // An edit still waiting to be sent would land after the reset and undo part of it.
            changeSetting.cancel();
            api.resetSettings();
          }}
        >
          <UpdatesBlock
            settings={state.settings}
            update={state.update}
            version={state.version}
            isPortable={Boolean(state.isPortable)}
            onChange={changeSetting}
            onCheck={() => api.checkForUpdates()}
            onUnskip={() => api.skipUpdate("")}
          />
        </SettingsBlock>
      </>
    ),
  };

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

      {/* Until there is a route the card has nothing to show: the two steps to one take its
          place. The map area is not one of them -- the first Start asks for it. */}
      {state.routes.length === 0 ? (
        <FirstRun onDraw={() => api.openEditor("")} />
      ) : (
        <HeroCard
          route={route}
          progress={state.progress}
          region={state.region}
          nextIcon={pointIcons[Math.min(state.progress.done, state.progress.total)] ?? null}
        >
          <Status running={state.running} />
        </HeroCard>
      )}

      <RunRow
        running={state.running}
        canStart={Boolean(route) || state.settings.show_cubes}
        checklistVisible={state.steps.visible}
        overlayVisible={state.overlayVisible}
        captureVisible={state.captureVisible}
        captureExclusion={state.captureExclusion}
        onStart={() => api.start()}
        onStop={() => api.stop()}
        onChecklistVisible={(visible) => api.setStepsVisible(visible)}
        onOverlayVisible={(visible) => api.setOverlayVisible(visible)}
        onCaptureVisible={(visible) => api.setCaptureVisible(visible)}
      />
      <OverlayFilters
        cubes={state.settings.show_cubes}
        traces={state.settings.route_traces}
        seals={state.settings.route_seals}
        onCubes={(on) => changeSetting("show_cubes", on)}
        onTraces={(on) => changeSetting("route_traces", on)}
        onSeals={(on) => changeSetting("route_seals", on)}
      />
      <SearchHint running={state.running} />

      <PanelMenu
        active={section}
        onSelect={setSection}
        onEditor={() => api.openEditor(state.route ?? "")}
        updateWaiting={updateWaiting}
      />

      <div {...panel(section)}>{content[section]}</div>

      {/* The other sections, drawn once and unseen while the panel opens: their first drawing
          used to freeze the panel on the first click */}
      <WarmUp>
        {SECTIONS.filter((id) => id !== section).map((id) => (
          <div key={id} className="pn-section">
            {content[id]}
          </div>
        ))}
      </WarmUp>

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
