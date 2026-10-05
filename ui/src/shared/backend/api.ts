/**
 * The only place that knows the channel speaks JSON.
 *
 * Components call `api.saveRoute(id, doc)` and get a typed object back. Nothing above this
 * file stringifies, parses, or touches the raw Qt object -- which is what lets the mock be a
 * drop-in, and what stops a component from depending on a slot name.
 */

import type {
  AppState,
  BackendObject,
  EditorRequest,
  ObjectSet,
  RouteDoc,
  SaveResult,
  Settings,
  StepsData,
  StepsObject,
  StepsSize,
  TimerChoice,
} from "./contract";
import { safeParse } from "./json";
import { call } from "./transport";

export interface BackendApi {
  getState(): Promise<AppState | null>;
  refreshRoutes(): void;

  start(): void;
  stop(): void;
  setPreview(enabled: boolean): void;
  updateSettings(patch: Partial<Settings>): void;
  resetSettings(): void;
  setOverlayVisible(visible: boolean): void;
  setCaptureVisible(visible: boolean): void;
  setPlayerAnchor(fx: number, fy: number): void;

  selectRegion(): void;
  resetRegion(): void;

  setRoute(routeId: string): void;
  deleteRoute(routeId: string): void;
  reorderRoutes(routeIds: string[]): void;
  saveRoute(id: string | null, doc: RouteDoc): Promise<SaveResult>;
  exportRoute(routeId: string): void;
  importRouteFile(): void;
  copyRouteCode(routeId: string): void;
  pasteRouteCode(): void;

  setProgress(done: number): void;
  resetProgress(): void;

  setStepsVisible(visible: boolean): void;
  setStepsPinned(pinned: boolean): void;
  setStepsSize(size: StepsSize): void;

  openEditor(routeId: string): void;
  closeEditor(): void;
  getEditorRoute(): Promise<EditorRequest | null>;

  getObjects(mapId: string): Promise<ObjectSet[]>;

  openRoutesFolder(): void;
  openMapsFolder(): void;
  openLogsFolder(): void;
  openUrl(url: string): void;
  copyText(text: string): void;

  checkForUpdates(): void;
  downloadUpdate(): void;
  installUpdate(restart: boolean): void;
  skipUpdate(version: string): void;

  setTimerEvent(eventId: string, choice: Partial<TimerChoice>): void;
  setTimersWorldShown(ids: string[]): void;
  refreshTimersData(): void;
}

export function createBackendApi(object: BackendObject): BackendApi {
  return {
    getState: () =>
      call<string>(object, "getState").then((j) => safeParse<AppState | null>(j, null)),
    refreshRoutes: () => object.refreshRoutes(),

    start: () => object.start(),
    stop: () => object.stop(),
    setPreview: (enabled) => object.setPreview(enabled),
    updateSettings: (patch) => object.updateSettings(JSON.stringify(patch)),
    resetSettings: () => object.resetSettings(),
    setOverlayVisible: (visible) => object.setOverlayVisible(visible),
    setCaptureVisible: (visible) => object.setCaptureVisible(visible),
    setPlayerAnchor: (fx, fy) => object.setPlayerAnchor(fx, fy),

    selectRegion: () => object.selectRegion(),
    resetRegion: () => object.resetRegion(),

    setRoute: (routeId) => object.setRoute(routeId),
    deleteRoute: (routeId) => object.deleteRoute(routeId),
    reorderRoutes: (routeIds) => object.reorderRoutes(JSON.stringify(routeIds)),
    saveRoute: (id, doc) =>
      call<string>(object, "saveRoute", JSON.stringify({ id, doc })).then((j) =>
        safeParse<SaveResult>(j, { ok: false, code: "route.save_failed" }),
      ),
    exportRoute: (routeId) => object.exportRoute(routeId),
    importRouteFile: () => object.importRouteFile(),
    copyRouteCode: (routeId) => object.copyRouteCode(routeId),
    pasteRouteCode: () => object.pasteRouteCode(),

    setProgress: (done) => object.setProgress(done),
    resetProgress: () => object.resetProgress(),

    setStepsVisible: (visible) => object.setStepsVisible(visible),
    setStepsPinned: (pinned) => object.setStepsPinned(pinned),
    setStepsSize: (size) => object.setStepsSize(size),

    openEditor: (routeId) => object.openEditor(routeId),
    closeEditor: () => object.closeEditor(),
    getEditorRoute: () =>
      call<string>(object, "getEditorRoute").then((j) => safeParse<EditorRequest | null>(j, null)),

    getObjects: (mapId) =>
      call<string>(object, "getObjects", mapId).then((j) => safeParse<ObjectSet[]>(j, [])),

    openRoutesFolder: () => object.openRoutesFolder(),
    openMapsFolder: () => object.openMapsFolder(),
    openLogsFolder: () => object.openLogsFolder(),
    openUrl: (url) => object.openUrl(url),
    copyText: (text) => object.copyText(text),

    checkForUpdates: () => object.checkForUpdates(),
    downloadUpdate: () => object.downloadUpdate(),
    installUpdate: (restart) => object.installUpdate(restart),
    skipUpdate: (version) => object.skipUpdate(version),

    setTimerEvent: (eventId, choice) => object.setTimerEvent(eventId, JSON.stringify(choice)),
    setTimersWorldShown: (ids) => object.setTimersWorldShown(JSON.stringify(ids)),
    refreshTimersData: () => object.refreshTimersData(),
  };
}

export interface StepsApi {
  getData(): Promise<StepsData | null>;
  dragStart(): void;
  dragEnd(): void;
  /** "prev" and "next" since api 11: the route before or after the open one. */
  action(name: "size" | "pin" | "close" | "prev" | "next"): void;
  setHeight(height: number): void;
  setHotspot(x: number, y: number, w: number, h: number): void;
}

export function createStepsApi(object: StepsObject): StepsApi {
  return {
    getData: () =>
      call<string>(object, "getData").then((j) => safeParse<StepsData | null>(j, null)),
    dragStart: () => object.dragStart(),
    dragEnd: () => object.dragEnd(),
    action: (name) => object.action(name),
    setHeight: (height) => object.setHeight(height),
    setHotspot: (x, y, w, h) => object.setHotspot(x, y, w, h),
  };
}
