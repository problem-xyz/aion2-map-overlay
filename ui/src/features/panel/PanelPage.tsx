import { memo, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState, MapInfo, ProgressState, RouteInfo } from "@/shared/backend/contract";
import { useApi } from "@/shared/backend/hooks";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { useT } from "@/shared/i18n";

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
import WarmUp from "./components/WarmUp";
import { usePointIcons } from "./hooks/usePointIcons";

const SECTION_KEY = "mo.panel.section";
const SECTIONS: readonly PanelSection[] = ["routes", "progress", "settings"];
// The sections that were folded into another: a panel last left on one opens on its new home
const FOLDED: Readonly<Record<string, PanelSection>> = { steps: "progress", area: "settings" };
const NO_PROGRESS: ProgressState = { done: 0, total: 0, map: null, markers: [] };

/**
 * The resources the filter's list offers: the route's map's. With no route followed the engine
 * finds the open map itself, so every map's are offered, each once, in the order they are listed.
 */
function mapResources(maps: readonly MapInfo[], mapId: string | undefined): string[] {
  const on = mapId ? maps.filter((m) => m.id === mapId) : maps;
  return [...new Set(on.flatMap((m) => m.resources ?? []))];
}

// The map tool shows neither the updater nor the timers, and a download in progress changes the
// first several times a second: the state is kept as it was when only those moved.
const NOT_SHOWN: ReadonlySet<string> = new Set(["update", "timers", "timersPlaque"]);

export function sameForPanel(a: AppState, b: AppState): boolean {
  const keys = Object.keys(b) as (keyof AppState)[];
  return (
    keys.length === Object.keys(a).length && keys.every((k) => NOT_SHOWN.has(k) || a[k] === b[k])
  );
}

function loadSection(): PanelSection {
  try {
    const stored = window.localStorage.getItem(SECTION_KEY) ?? "";
    return SECTIONS.find((s) => s === stored) ?? FOLDED[stored] ?? "routes";
  } catch {
    return "routes";
  }
}

/**
 * The map tool of the control panel (app/ControlPage.tsx holds the switch between the tools).
 *
 * It holds no copy of the backend state: every field is read through a selector, so a stats
 * tick at 10 Hz re-renders the status strip and nothing else. What it does own is the one piece
 * of state the backend has no opinion about: whether the preview is switched on.
 */
function PanelPage() {
  const api = useApi();
  const t = useT();
  const confirm = useConfirm();
  const changeSetting = useSettingsPatch();
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

  const shown = useRef<AppState | null>(null);
  const state = useBackendState<AppState, AppState | null>((s) => {
    if (s && shown.current && sameForPanel(shown.current, s)) return shown.current;
    return (shown.current = s);
  });

  const togglePreview = useCallback(
    (on: boolean) => {
      setPreviewOn(on);
      api?.setPreview(on);
    },
    [api],
  );

  // Switching to the other tool unmounts this page: a preview left on would go on streaming
  // frames nobody sees.
  const previewLive = useRef({ on: previewOn, api });
  previewLive.current = { on: previewOn, api };
  useEffect(
    () => () => {
      if (previewLive.current.on) previewLive.current.api?.setPreview(false);
    },
    [],
  );

  // Stable, so that the route list -- thumbnails and all -- sits out a slider drag.
  const activeRoute = state?.route ?? null;
  const routeActions = useMemo(
    () => ({
      onSelect: (id: string) => api?.setRoute(id),
      onEditor: () => api?.openEditor(activeRoute ?? ""),
      onNew: () => api?.openEditor(""),
      onEdit: (id: string) => api?.openEditor(id),
      onDelete: (r: RouteInfo) => {
        void confirm(t("panel.routes.confirmDelete", { label: r.label }), {
          confirmLabel: t("panel.routes.deleteTip"),
          danger: true,
        }).then((ok) => {
          if (ok) api?.deleteRoute(r.id);
        });
      },
      onReorder: (ids: string[]) => api?.reorderRoutes(ids),
      onImport: () => api?.importRouteFile(),
      onPaste: () => api?.pasteRouteCode(),
      onOpenFolder: () => api?.openRoutesFolder(),
    }),
    [api, activeRoute, confirm, t],
  );

  const route = state?.routes.find((r) => r.id === state.route);
  const pointIcons = usePointIcons(route?.map, state?.progress ?? NO_PROGRESS);

  if (!state || !api) return null;

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
        <RoutesList routes={state.routes} active={state.route} {...routeActions} />
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
        />
      </>
    ),
  };

  return (
    <>
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
        canStart={
          (Boolean(route) && state.settings.route_mode) ||
          state.settings.show_cubes ||
          (state.settings.show_resources && state.settings.resources.length > 0)
        }
        checklistVisible={state.steps.visible}
        routeMode={state.settings.route_mode}
        captureVisible={state.captureVisible}
        captureExclusion={state.captureExclusion}
        onStart={() => api.start()}
        onStop={() => api.stop()}
        onChecklistVisible={(visible) => api.setStepsVisible(visible)}
        onRouteMode={(on) => changeSetting("route_mode", on)}
        onCaptureVisible={(visible) => api.setCaptureVisible(visible)}
      />
      <OverlayFilters
        cubes={state.settings.show_cubes}
        resources={state.settings.show_resources}
        picked={state.settings.resources}
        available={mapResources(state.maps, state.settings.route_mode ? route?.map : undefined)}
        traces={state.settings.route_traces}
        seals={state.settings.route_seals}
        onCubes={(on) => changeSetting("show_cubes", on)}
        onResources={(on) => changeSetting("show_resources", on)}
        onPick={(ids) => changeSetting("resources", ids)}
        onTraces={(on) => changeSetting("route_traces", on)}
        onSeals={(on) => changeSetting("route_seals", on)}
      />
      <SearchHint running={state.running} />

      <PanelMenu
        active={section}
        onSelect={setSection}
        onEditor={() => api.openEditor(state.route ?? "")}
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
    </>
  );
}

// The control page around it re-renders for the update banner, which is not in here.
export default memo(PanelPage);
