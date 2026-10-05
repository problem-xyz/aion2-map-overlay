/**
 * A stand-in for the Python objects, so the UI can be opened in an ordinary browser.
 *
 * It is not a test double bolted on afterwards: it implements the same surface the real
 * channel exposes -- slots as plain functions, signals as {connect, disconnect} -- so nothing
 * above `transport.ts` can tell them apart. That is the only way the mock stays honest, and
 * it is what lets design work happen without a running game.
 *
 * Only ever loaded behind `import.meta.env.DEV`, so the bundler drops it from a build.
 */

import type {
  AppState,
  NotifyPayload,
  RouteDoc,
  Settings,
  TimerChoice,
  UpdateState,
} from "@/shared/backend/contract";

import {
  MOCK_OBJECT_SETS,
  MOCK_ROUTE,
  MOCK_SETTINGS_SCHEMA,
  MOCK_UPDATE,
  makeState,
  makeStepsData,
} from "./mockState";
import { makeTimers } from "./mockTimers";
import {
  applyScenario,
  loadObjectSets,
  localTiles,
  readScenario,
  referenceImage,
  scenarioNotices,
  type Scenario,
} from "./scenarios";

type Handler = (...args: unknown[]) => void;

interface MockSignal {
  connect: (h: Handler) => void;
  disconnect: (h: Handler) => void;
  emit: (...args: unknown[]) => void;
}

function signal(): MockSignal {
  const handlers = new Set<Handler>();
  return {
    connect: (h: Handler) => void handlers.add(h),
    disconnect: (h: Handler) => void handlers.delete(h),
    emit: (...args: unknown[]) => handlers.forEach((h) => h(...args)),
  };
}

/**
 * The signal names are spelled out rather than left open: otherwise every `signals.x` would be
 * possibly undefined and need a check at the call site.
 */
type MockSignals = Record<
  | "stateChanged"
  | "statsChanged"
  | "previewChanged"
  | "notify"
  | "editorRequest"
  | "progressChanged"
  | "stepsChanged"
  | "updateChanged"
  | "timersChanged"
  | "dataChanged",
  MockSignal
>;

interface MockRuntime {
  scenario: Scenario;
  /** The scenario's notices went out: StrictMode connects twice, and they must show once. */
  noticesSent: boolean;
  state: AppState;
  editorDoc: RouteDoc;
  editorId: string | null;
  editorSeq: number;
  signals: MockSignals;
  statsTimer: ReturnType<typeof setInterval> | null;
  updateTimer: ReturnType<typeof setTimeout> | null;
  timersTimer: ReturnType<typeof setInterval> | null;
}

let runtime: MockRuntime | null = null;

function boot(): MockRuntime {
  if (runtime) return runtime;
  runtime = {
    scenario: readScenario(window.location.search),
    noticesSent: false,
    state: makeState(),
    editorDoc: structuredClone(MOCK_ROUTE),
    editorId: "altgard-loop",
    editorSeq: 0,
    signals: {
      stateChanged: signal(),
      statsChanged: signal(),
      previewChanged: signal(),
      notify: signal(),
      editorRequest: signal(),
      progressChanged: signal(),
      stepsChanged: signal(),
      updateChanged: signal(),
      timersChanged: signal(),
      dataChanged: signal(),
    },
    statsTimer: null,
    updateTimer: null,
    timersTimer: null,
  };
  applyScenario(runtime.state, runtime.editorDoc, runtime.scenario);
  pushTimers(runtime);
  // As Python's tick: the timers are worked out again every so often, the page counts the seconds
  const rt = runtime;
  rt.timersTimer = setInterval(() => pushTimers(rt), 15_000);
  void takeLocalFiles(runtime);
  return runtime;
}

/**
 * Swaps in what this machine has: the tiles the app cut into userdata/ and the real object
 * sets. Without them the editor still opens, on a blank map with a handful of points.
 */
async function takeLocalFiles(rt: MockRuntime) {
  let changed = false;
  for (const map of rt.state.maps) {
    const [tiles, sets] = await Promise.all([localTiles(map.id), loadObjectSets(map.id)]);
    if (tiles) {
      map.tilesUrl = tiles.url;
      map.size = [4096, 4096];
      // a pyramid cut from a map's 8192 px detail image is one level deeper than the map
      map.tiles = {
        ready: !rt.state.tilesBusy.includes(map.id),
        zMax: 4,
        tile: 256,
        zNative: tiles.zMax,
      };
      changed = true;
    }
    if (sets) {
      map.objects = sets.map((s) => ({
        file: s.file,
        mapName: s.mapName,
        nodes: s.nodes.length,
        bundled: true,
      }));
      changed = true;
    }
  }
  if (changed) pushState(rt);
}

function pushState(rt: MockRuntime) {
  rt.signals.stateChanged.emit(JSON.stringify(rt.state));
}

/** The timers at the mock's clock: now, moved by the scenario's `shift` minutes. */
function pushTimers(rt: MockRuntime, fetching = false) {
  const now = Date.now() + rt.scenario.shift * 60_000;
  rt.state.timers = makeTimers(rt.state.settings, now, fetching);
  rt.signals.timersChanged.emit(JSON.stringify(rt.state.timers));
}

function pushSteps(rt: MockRuntime) {
  rt.signals.stepsChanged.emit(JSON.stringify(rt.state.steps));
  rt.signals.dataChanged.emit(JSON.stringify(makeStepsData(rt.state)));
}

function notify(rt: MockRuntime, payload: NotifyPayload) {
  rt.signals.notify.emit(JSON.stringify(payload));
}

function startStats(rt: MockRuntime) {
  if (rt.statsTimer) return;
  let frame = 0;
  rt.statsTimer = setInterval(() => {
    frame += 1;
    rt.signals.statsChanged.emit(
      JSON.stringify({
        found: true,
        anchored: frame % 8 !== 0,
        fps: 58 + (frame % 3),
        processMs: 9 + (frame % 4),
        detectMs: 120 + (frame % 20),
        flowPoints: 180 + (frame % 15),
        matches: 240 + (frame % 30),
        inliers: 90 + (frame % 10),
        reprojError: Math.round((2.1 + (frame % 5) / 10) * 100) / 100,
        backend: "dxcam",
      }),
    );
  }, 100);
}

function stopStats(rt: MockRuntime) {
  if (rt.statsTimer) clearInterval(rt.statsTimer);
  rt.statsTimer = null;
}

/** As Python does it: updateChanged on every change, the whole state only on a new phase. */
function setUpdate(rt: MockRuntime, next: UpdateState) {
  const newPhase = rt.state.update?.phase !== next.phase;
  rt.state.update = next;
  rt.signals.updateChanged.emit(JSON.stringify(next));
  if (newPhase) pushState(rt);
}

function isSkipped(rt: MockRuntime) {
  return rt.state.settings.updates_skipped_version === MOCK_UPDATE.version;
}

function mockDownload(rt: MockRuntime) {
  let progress = 0;
  const tick = () => {
    if (progress > 100) {
      rt.updateTimer = null;
      setUpdate(rt, { phase: "ready", ...MOCK_UPDATE, skipped: isSkipped(rt) });
      notify(rt, { level: "info", code: "update.ready", params: { version: MOCK_UPDATE.version } });
      return;
    }
    setUpdate(rt, { phase: "downloading", ...MOCK_UPDATE, skipped: false, progress });
    progress += 10;
    rt.updateTimer = setTimeout(tick, 150);
  };
  tick();
}

function mockCheck(rt: MockRuntime) {
  setUpdate(rt, { phase: "checking" });
  rt.updateTimer = setTimeout(() => {
    rt.updateTimer = null;
    const skipped = isSkipped(rt);
    if (!skipped && rt.state.settings.updates_auto_download) {
      mockDownload(rt);
      return;
    }
    // No notice, as in Python: the banner shows it.
    setUpdate(rt, { phase: "available", ...MOCK_UPDATE, skipped });
  }, 600);
}

function backendObject(rt: MockRuntime) {
  return {
    ...rt.signals,

    getState: (cb: (j: string) => void) => cb(JSON.stringify(rt.state)),
    refreshRoutes: () => pushState(rt),

    start: () => {
      // As Backend.start: with no map area yet, the first Start asks for one and then runs
      if (!rt.state.region) {
        rt.state.region = { left: 100, top: 100, width: 900, height: 700 };
        notify(rt, { level: "info", code: "region.selected", text: "Area selected: 900 x 700" });
      }
      rt.state.running = true;
      startStats(rt);
      pushState(rt);
    },
    stop: () => {
      rt.state.running = false;
      stopStats(rt);
      rt.signals.previewChanged.emit("");
      pushState(rt);
    },
    setPreview: () => {},
    updateSettings: (json: string) => {
      Object.assign(rt.state.settings, JSON.parse(json));
      pushTimers(rt);
      pushState(rt);
      pushSteps(rt); // the plaque's scale and opacity are settings too
    },
    resetSettings: () => {
      // Defaults come from the schema, the way Python's come from the dataclass; the updater's
      // fields survive, as they do in SettingsStore.reset_settings.
      const { updates_auto_check, updates_auto_download, updates_skipped_version } =
        rt.state.settings;
      const defaults = Object.fromEntries(
        Object.entries(MOCK_SETTINGS_SCHEMA).map(([key, field]) => [key, field.default]),
      ) as unknown as Settings;
      rt.state.settings = {
        ...defaults,
        updates_auto_check,
        updates_auto_download,
        updates_skipped_version,
      };
      rt.state.captureVisible = rt.state.settings.capture_visible;
      rt.state.steps.pinned = rt.state.settings.steps_pinned;
      rt.state.steps.size = rt.state.settings.steps_size;
      notify(rt, {
        level: "info",
        code: "settings.reset",
        text: "Settings are back to their defaults.",
      });
      pushState(rt);
      pushSteps(rt);
    },
    setOverlayVisible: (v: boolean) => {
      rt.state.overlayVisible = v;
      pushState(rt);
    },
    setCaptureVisible: (v: boolean) => {
      rt.state.captureVisible = v;
      rt.state.settings.capture_visible = v;
      pushState(rt);
    },
    setPlayerAnchor: (fx: number, fy: number) => {
      rt.state.settings.player_anchor_x = fx;
      rt.state.settings.player_anchor_y = fy;
      pushState(rt);
    },

    selectRegion: () => {
      rt.state.region = { left: 100, top: 100, width: 900, height: 700 };
      notify(rt, { level: "info", code: "region.selected", text: "Area selected: 900 x 700" });
      pushState(rt);
    },
    resetRegion: () => {
      rt.state.running = false;
      rt.state.region = null;
      pushState(rt);
    },

    setRoute: (id: string) => {
      rt.state.route = id;
      pushState(rt);
      pushSteps(rt);
    },
    deleteRoute: (id: string) => {
      rt.state.routes = rt.state.routes.filter((r) => r.id !== id);
      if (rt.state.route === id) rt.state.route = rt.state.routes[0]?.id ?? null;
      pushState(rt);
    },
    reorderRoutes: (payload: string) => {
      const ids = JSON.parse(payload) as string[];
      const rank = (id: string) => {
        const at = ids.indexOf(id);
        return at === -1 ? ids.length : at;
      };
      rt.state.routes = [...rt.state.routes].sort((a, b) => rank(a.id) - rank(b.id));
      pushState(rt);
    },
    saveRoute: (payload: string, cb: (j: string) => void) => {
      const { id, doc } = JSON.parse(payload) as { id: string | null; doc: RouteDoc };
      rt.editorDoc = doc;
      const routeId = id ?? "new-route";
      rt.editorId = routeId;
      notify(rt, { level: "info", code: "route.saved", text: `Route "${doc.name}" saved.` });
      pushState(rt);
      cb(JSON.stringify({ ok: true, id: routeId }));
    },
    exportRoute: () =>
      notify(rt, { level: "info", code: "route.exported", text: "Route exported." }),
    importRouteFile: () =>
      notify(rt, {
        level: "info",
        code: "route.imported.file",
        params: { name: "Imported" },
        text: "Route “Imported” added from a file.",
      }),
    copyRouteCode: () =>
      notify(rt, {
        level: "info",
        code: "share.copied",
        text: "Route code copied (412 characters).",
      }),
    pasteRouteCode: () =>
      notify(rt, {
        level: "error",
        code: "share.not_a_code",
        text: "That is not a route code for this app.",
      }),

    setProgress: (done: number) => {
      rt.state.progress.done = done;
      rt.signals.progressChanged.emit(JSON.stringify({ done, total: rt.state.progress.total }));
      pushSteps(rt);
    },
    resetProgress: () => {
      rt.state.progress.done = 0;
      rt.signals.progressChanged.emit(JSON.stringify({ done: 0, total: rt.state.progress.total }));
      pushSteps(rt);
    },

    setStepsVisible: (v: boolean) => {
      rt.state.steps.visible = v;
      pushState(rt);
      pushSteps(rt);
    },
    setStepsPinned: (v: boolean) => {
      rt.state.steps.pinned = v;
      rt.state.settings.steps_pinned = v;
      pushState(rt);
      pushSteps(rt);
    },
    setStepsSize: (size: string) => {
      rt.state.steps.size = size as AppState["steps"]["size"];
      rt.state.settings.steps_size = rt.state.steps.size;
      rt.state.settings.steps_scale = { s: 0.5, m: 0.5, l: 0.86 }[rt.state.steps.size];
      pushState(rt);
      pushSteps(rt);
    },

    openEditor: (id: string) => {
      rt.state.editorOpen = true;
      rt.editorId = id || null;
      rt.signals.editorRequest.emit(
        JSON.stringify({ seq: ++rt.editorSeq, id: rt.editorId, doc: rt.editorDoc }),
      );
      pushState(rt);
    },
    closeEditor: () => {
      rt.state.editorOpen = false;
      pushState(rt);
    },
    getEditorRoute: (cb: (j: string) => void) =>
      cb(JSON.stringify({ seq: ++rt.editorSeq, id: rt.editorId, doc: rt.editorDoc })),

    getObjects: (id: string, cb: (j: string) => void) =>
      void loadObjectSets(id).then((sets) =>
        cb(JSON.stringify(sets ?? MOCK_OBJECT_SETS[id] ?? [])),
      ),

    openRoutesFolder: () => {},
    openMapsFolder: () => {},
    openLogsFolder: () => {},
    // A browser tab would leave the mock page; logging it is enough to see the call.
    openUrl: (url: string) => console.info("[mock] openUrl", url),
    copyText: (text: string) => void navigator.clipboard?.writeText(text).catch(() => {}),

    // The same guards as updater/service.py: a request that does not fit the phase is ignored.
    checkForUpdates: () => {
      const phase = rt.state.update?.phase ?? "idle";
      if (rt.updateTimer || phase === "disabled" || (phase === "ready" && !isSkipped(rt))) return;
      mockCheck(rt);
    },
    downloadUpdate: () => {
      const phase = rt.state.update?.phase;
      if (rt.updateTimer || (phase !== "available" && phase !== "failed")) return;
      if (isSkipped(rt)) rt.state.settings.updates_skipped_version = "";
      mockDownload(rt);
    },
    installUpdate: (restart: boolean) => {
      if (rt.updateTimer || rt.state.update?.phase !== "ready") return;
      if (isSkipped(rt)) rt.state.settings.updates_skipped_version = "";
      if (restart) {
        // The real app ends here and comes back on the new version; the mock only pretends.
        rt.state.version = MOCK_UPDATE.version;
        setUpdate(rt, { phase: "none" });
        return;
      }
      setUpdate(rt, { ...rt.state.update, skipped: false });
      notify(rt, { level: "info", code: "update.ready", params: { version: MOCK_UPDATE.version } });
    },
    skipUpdate: (version: string) => {
      rt.state.settings.updates_skipped_version = version;
      const current = rt.state.update;
      if (current?.version !== undefined) {
        setUpdate(rt, { ...current, skipped: current.version === version });
      }
      pushState(rt);
    },

    setTimerEvent: (eventId: string, json: string) => {
      const events = rt.state.settings.timers_events;
      events[eventId] = { ...events[eventId], ...(JSON.parse(json) as Partial<TimerChoice>) };
      pushTimers(rt);
      pushState(rt);
    },
    setTimersWorldShown: (json: string) => {
      rt.state.settings.timers_world_shown = JSON.parse(json) as string[];
      pushTimers(rt);
      pushState(rt);
    },
    previewTimerSignal: () => {},
    refreshTimersData: () => {
      // a fetch that finds nothing newer, after a moment
      pushTimers(rt, true);
      setTimeout(() => pushTimers(rt), 900);
    },
  };
}

function stepsObject(rt: MockRuntime) {
  return {
    dataChanged: rt.signals.dataChanged,
    getData: (cb: (j: string) => void) => cb(JSON.stringify(makeStepsData(rt.state))),
    dragStart: () => {},
    dragEnd: () => {},
    action: (name: string) => {
      if (name === "close") rt.state.steps.visible = false;
      if (name === "pin") rt.state.steps.pinned = !rt.state.steps.pinned;
      if (name === "prev" || name === "next") {
        // as Backend._step_progress: one point back or forward, within the route
        const { done, total } = rt.state.progress;
        const step = name === "next" ? 1 : -1;
        rt.state.progress.done = Math.max(0, Math.min(done + step, total));
        rt.signals.progressChanged.emit(JSON.stringify({ done: rt.state.progress.done, total }));
      }
      if (name === "size") {
        const order = ["s", "m", "l"] as const;
        const next = (order.indexOf(rt.state.steps.size) + 1) % order.length;
        rt.state.steps.size = order[next] ?? "m";
      }
      pushState(rt);
      pushSteps(rt);
    },
    setHeight: () => {},
    setHotspot: () => {},
  };
}

export function createMockObject(name: string): unknown {
  const rt = boot();
  const object = name === "steps" ? stepsObject(rt) : backendObject(rt);

  if (name !== "steps" && !rt.noticesSent) {
    rt.noticesSent = true;
    // After the page has had a moment to subscribe: a notice nobody listens to is lost
    const notices = scenarioNotices(rt.scenario);
    if (notices.length) setTimeout(() => notices.forEach((n) => notify(rt, n)), 600);
  }
  void referenceImage(rt.scenario.bg).then((url) => {
    // Behind the page itself: only the plaque is transparent, so only it shows the game
    if (url) document.documentElement.style.background = `#000 url("${url}") center / cover`;
  });

  // A handle for driving scenarios from the browser console: window.__mock.emit("notify", {...})
  window.__mock = {
    emit: (signalName: string, payload: unknown) => {
      const target = (rt.signals as Record<string, MockSignal | undefined>)[signalName];
      target?.emit(typeof payload === "string" ? payload : JSON.stringify(payload));
    },
    patchState: (fn: (s: AppState) => void) => {
      fn(rt.state);
      pushState(rt);
      pushSteps(rt);
    },
    state: () => rt.state,
  };

  return object;
}
