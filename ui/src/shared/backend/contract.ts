/**
 * The typed boundary with Python.
 *
 * This file mirrors `bridge/state.py` and the slot table in `bridge/backend.py`. Those are the
 * source of truth; if the two disagree, Python wins and this file is wrong. Keeping the shape
 * written down here is what lets a component say `state.region` and be told when that stops
 * being true, instead of finding out at runtime in a QWebEngineView with no console.
 *
 * Everything crossing the channel is a JSON string. Parsing happens once, in api.ts.
 */

import type { ObjectIconName } from "@/shared/ui/markIcons";

export interface Region {
  left: number;
  top: number;
  width: number;
  height: number;
}

export type RouteView = "steps" | "dim" | "all";
export type EditorRouteView = Exclude<RouteView, "steps">;

export interface Settings {
  opacity: number;
  fps: number;
  detector: "sift" | "orb";
  detect_scale: number;
  min_inliers: number;
  transform: "similarity" | "homography";
  tracking: "flow" | "detect";
  smoothing: number;
  detect_interval: number;
  flow_points: number;
  hold_frames: number;
  /**
   * Since api 12: how much of the route the overlay draws. "steps" the next `route_ahead` steps
   * in full and the last `route_past` passed faded, nothing further; "dim" the whole route,
   * faded away from the next steps; "all" the whole route ahead in full, what was passed faded.
   */
  route_view: RouteView;
  route_ahead: number;
  route_past: number;
  /**
   * Since api 13: the same in the route editor, which always draws every point. "dim" fades the
   * route away from the selected point and `editor_route_ahead` steps from it; "all" draws it
   * all in full. `editor_opacity` is the lines' and arrows' opacity there.
   */
  editor_route_view: EditorRouteView;
  editor_route_ahead: number;
  editor_opacity: number;
  /** Read by nothing since api 16: progress always counts. Kept because Python still sends it. */
  progress_enabled: boolean;
  auto_progress: boolean;
  player_anchor_x: number;
  player_anchor_y: number;
  arrive_radius: number;
  ratio: number;
  reproj_thr: number;
  ref_features: number;
  frame_features: number;
  capture_visible: boolean;
  steps_pinned: boolean;
  steps_size: StepsSize;
  /**
   * Since api 11: the plaque's size on the panel's slider, 0.5-1.5. Python draws it at the factor
   * that stands for (plaque_scale in core/settings.py) and sends that factor as StepsData.scale.
   */
  steps_scale: number;
  language: "auto" | "en" | "ru";
  updates_auto_check: boolean;
  updates_auto_download: boolean;
  updates_skipped_version: string;
}

/**
 * One setting as `settings_schema()` in core/settings.py describes it.
 *
 * `min`/`max` are the range Python clamps every value to, on load and on every updateSettings, so
 * a control that reads them offers exactly what the file accepts. They exist only on a ranged
 * field, and `choices` only on one with a fixed list.
 */
export interface SettingSchema {
  type: "bool" | "int" | "float" | "str";
  default: boolean | number | string;
  min?: number;
  max?: number;
  choices?: string[];
}

/** Partial: a backend older or newer than this build may describe fewer or more settings. */
export type SettingsSchema = Partial<Record<keyof Settings, SettingSchema>>;

export type StepsSize = "s" | "m" | "l";

export interface TilesInfo {
  ready: boolean;
  zMax: number;
  tile: number;
  /** Since api 10: the pyramid's deepest level, past zMax, when it is cut from a finer image. */
  zNative?: number;
}

/** An object set as `getState` lists it on a map: a summary, without the points. */
export interface ObjectSetInfo {
  file: string;
  mapName: string;
  nodes: number;
  /** Ships with the app for this map: always there, and cannot be removed. Api 7. */
  bundled?: boolean;
}

export interface ObjectCategory {
  id: string;
  name: string;
  parentId: string | null;
  color: string;
}

/** A point of interest. Coordinates are percentages of the map, not pixels. */
export interface ObjectNode {
  c: string;
  x: number;
  y: number;
  t: string;
  d: string;
}

/**
 * A whole object set, as `getObjects` returns it -- categories and every point.
 *
 * Not the same shape as `ObjectSetInfo`, which is what `getState` puts on a map: that one
 * carries a node *count* where this one carries the nodes.
 */
export interface ObjectSet {
  file: string;
  mapName: string;
  categories: ObjectCategory[];
  nodes: ObjectNode[];
  /** As on ObjectSetInfo. Api 7. */
  bundled?: boolean;
}

/** Whose zone a map is. Absent before api 20. */
export type Faction = "asmodian" | "elyos";

export interface MapInfo {
  id: string;
  label: string;
  size: [number, number];
  faction?: Faction | null;
  thumb: string;
  tiles: TilesInfo;
  objects: ObjectSetInfo[];
  tilesUrl?: string;
}

export interface RouteInfo {
  id: string;
  label: string;
  map: string;
  mapLabel: string;
  markers: number;
  steps: number;
  thumb: string;
  /** The route's map's; null on a map the manifest names no side for. Absent before api 20. */
  faction?: Faction | null;
  /** A starter route exactly as a release shipped it: edited, it is the user's own. */
  official?: boolean;
}

/** A route point's quest icon beside its number: a main quest (a yellow star) or a side one. */
export type MarkerIcon = "main" | "side";

export interface Marker {
  x: number;
  y: number;
  text: string;
  color?: string;
  /** Since api 9. */
  icon?: MarkerIcon;
}

export interface RouteStyle {
  color: string;
  width: number;
}

export interface RouteDoc {
  format: string;
  version: number;
  name: string;
  map: string;
  mapSize: [number, number];
  markers: Marker[];
  style: RouteStyle;
}

export interface StepsState {
  visible: boolean;
  region: Region | null;
  pinned: boolean;
  size: StepsSize;
}

export interface ProgressMarker {
  n: number;
  text: string;
  color: string;
  /** Since api 11: where the point is, in map pixels -- what the panel finds its object by. */
  x?: number;
  y?: number;
  /** Since api 11: the point's quest icon, where it has one. */
  icon?: MarkerIcon;
}

export interface ProgressState {
  done: number;
  total: number;
  map: [number, number] | null;
  markers: ProgressMarker[];
}

export interface AppState {
  version: string;
  /** Bumped by Python when a slot or payload key is added. Absent before api 2. */
  api?: number;
  running: boolean;
  overlayVisible: boolean;
  captureVisible: boolean;
  region: Region | null;
  route: string | null;
  routes: RouteInfo[];
  maps: MapInfo[];
  settings: Settings;
  captureBackend: string | null;
  platform: string;
  steps: StepsState;
  progress: ProgressState;
  editorOpen: boolean;
  tilesBusy: string[];
  dev: boolean;
  /**
   * A build told by portable.txt to keep everything beside itself. Absent before api 3, so it
   * is optional: a UI built against api 3 still has to run against an older backend.
   */
  isPortable?: boolean;
  /** The updater, as `updateChanged` also carries it. Absent before api 4. */
  update?: UpdateState;
  /** Ranges and defaults for every setting. Absent before api 5, like isPortable before 3. */
  settingsSchema?: SettingsSchema;
  /**
   * False on a Windows older than 10 version 2004, which cannot hide a window from capture: the
   * overlay is then always visible to recorders and to the engine. Absent before api 5, and
   * absent means it can.
   */
  captureExclusion?: boolean;
  /** The project's GitHub repository: the one site openUrl() opens pages of. Api 6. */
  repoUrl?: string;
  /** The exact addresses openUrl() opens beside the repository. Api 19. */
  links?: SupportLinks;
  /** The advertising banner that ships with the app, or null for none. Api 22. */
  banner?: BannerInfo | null;
}

export interface BannerInfo {
  /** The image's address, a file the app ships. */
  image: string;
  /** The page a click opens; openUrl() opens this exact address. */
  url: string;
  /** What the banner advertises: the image's alt text and tooltip. */
  label: string;
  /** A discount code offered to copy under the banner, and the discount it gives ("30%"). */
  code?: string;
  discount?: string;
}

export interface SupportLinks {
  /** The donation page. */
  donate: string;
  /** The invite to the players' Discord server. */
  discord: string;
  /** The invite to Aion 2 Global's Discord server, a community the project works with. Api 21. */
  partnerDiscord?: string;
}

export interface Stats {
  found: boolean;
  anchored: boolean;
  fps: number;
  processMs: number;
  detectMs: number | null;
  flowPoints: number;
  matches: number;
  inliers: number;
  reprojError: number | null;
  backend: string;
}

export type NotifyLevel = "info" | "warning" | "error";

export interface NotifyPayload {
  level: NotifyLevel;
  /** Stable code from i18n/catalog.py. Absent on payloads from an older backend. */
  code?: string;
  params?: Record<string, string | number>;
  /** English fallback, already formatted. Shown when there is no code or no key for it. */
  text?: string;
}

export interface SaveResult {
  ok: boolean;
  id?: string;
  error?: string;
  code?: string;
  params?: Record<string, string | number>;
}

export interface EditorRequest {
  seq: number;
  id: string | null;
  doc: RouteDoc | null;
}

export interface ProgressTick {
  done: number;
  total: number;
}

/** One entry of the steps plaque. Python sends objects, not tuples. */
export interface StepEntry {
  n: number;
  text: string;
  color: string;
  /** Since api 9: the point's quest icon, where it has one. */
  icon?: MarkerIcon;
  /** Since api 11: the icon of the object the point sits on, where it sits on one. */
  object?: ObjectIconName;
}

export interface StepsData {
  steps: StepEntry[];
  done: number;
  /** Since api 14: how many steps already passed the plaque lists, faded (settings.route_past). */
  past?: number;
  title: string;
  /** The old step nearest the scale, for a page from before api 11. */
  size: StepsSize;
  /** Since api 11: the factor the plaque is drawn at, worked out from settings.steps_scale. */
  scale?: number;
  pinned: boolean;
  /**
   * Since api 11: the plaque offers its arrows. Since api 16 it always does, and they take the
   * last point back and tick the next one off; before, they switched routes.
   */
  switch?: boolean;
  /**
   * Since api 18: how wide, in CSS pixels, the strips along the right and bottom edges are where
   * a press sizes the loose plaque. Python owns the gesture; the page only draws the cursors.
   */
  grip?: number;
  opacity: number;
  /** Resolved language for this window, e.g. "en". Python resolves `auto`, the page never does. */
  language: string;
}

/**
 * `disabled`: not a Velopack install (a source checkout, a copied build) -- nothing to offer.
 * `none`: the last check found nothing newer. `ready`: downloaded, and applied when the app
 * closes unless `skipped`, or at once through `installUpdate(true)`.
 */
export type UpdatePhase =
  "disabled" | "idle" | "checking" | "none" | "available" | "downloading" | "ready" | "failed";

/** Mirrors `UpdatePayload` in `updater/service.py`. */
export interface UpdateState {
  phase: UpdatePhase;
  /** With a known release: available, downloading, ready, and a failed download or install. */
  version?: string;
  /** The release notes, Markdown, as the release carries them. */
  notes?: string;
  /** The user chose to skip this version: no banner, and it is not applied on exit. */
  skipped?: boolean;
  /** 0-100, while downloading only. */
  progress?: number;
  /** When failed: the notify code whose sentence fits, with `reason` as its parameter. */
  code?: string;
  reason?: string;
  stage?: "check" | "download" | "install";
}

/**
 * The 39 slots on the `backend` object, exactly as Python declares them.
 *
 * Slots that return a value hand it back through a trailing callback, which is why these are
 * typed as callback-style here and promisified in api.ts. Do not change a signature: the
 * contract is frozen, and Python's docstring says the same thing from the other side.
 */
export interface BackendSlots {
  // state
  getState(cb: (json: string) => void): void;
  refreshRoutes(): void;

  // engine
  start(): void;
  stop(): void;
  setPreview(enabled: boolean): void;
  updateSettings(json: string): void;
  resetSettings(): void;
  setOverlayVisible(visible: boolean): void;
  setCaptureVisible(visible: boolean): void;
  setPlayerAnchor(fx: number, fy: number): void;

  // screen area
  selectRegion(): void;
  /** Since api 15: forgets the map area, stopping a running engine first. */
  resetRegion(): void;

  // routes
  setRoute(routeId: string): void;
  deleteRoute(routeId: string): void;
  /** Since api 17: JSON list of route ids, the order the panel lists them in. */
  reorderRoutes(payload: string): void;
  saveRoute(payload: string, cb: (json: string) => void): void;
  exportRoute(routeId: string): void;
  importRouteFile(): void;
  copyRouteCode(routeId: string): void;
  pasteRouteCode(): void;

  // progress
  setProgress(done: number): void;
  resetProgress(): void;

  // steps plaque
  setStepsVisible(visible: boolean): void;
  setStepsPinned(pinned: boolean): void;
  setStepsSize(size: string): void;

  // editor
  openEditor(routeId: string): void;
  closeEditor(): void;
  /** Returns the whole EditorRequest envelope, not a bare RouteDoc. */
  getEditorRoute(cb: (json: string) => void): void;

  // object sets ship with their map, as the maps ship with the app: they are only read (api 8)
  getObjects(mapId: string, cb: (json: string) => void): void;

  // folders
  openRoutesFolder(): void;
  openMapsFolder(): void;
  openLogsFolder(): void;
  /** Opens a page of the project's repository; Python refuses any other URL. Api 6. */
  openUrl(url: string): void;
  /** Puts a line of the page's text, a wallet address, on the clipboard. Api 19. */
  copyText(text: string): void;

  // updates (api 4)
  checkForUpdates(): void;
  downloadUpdate(): void;
  /** true: apply now and restart. false: apply when the app closes, as it would anyway. */
  installUpdate(restart: boolean): void;
  /** Do not offer this version again; "" forgets the skip. */
  skipUpdate(version: string): void;
}

export interface QtSignal<T extends unknown[] = [string]> {
  connect(handler: (...args: T) => void): void;
  disconnect(handler: (...args: T) => void): void;
}

export interface BackendSignals {
  stateChanged: QtSignal;
  statsChanged: QtSignal;
  previewChanged: QtSignal;
  notify: QtSignal;
  editorRequest: QtSignal;
  progressChanged: QtSignal;
  stepsChanged: QtSignal;
  /** JSON UpdateState on every change, download progress included. Api 4. */
  updateChanged: QtSignal;
}

export type BackendObject = BackendSlots & BackendSignals;

/** The `steps` object the plaque window talks to: six slots and one signal. */
export interface StepsSlots {
  getData(cb: (json: string) => void): void;
  /** The plaque has no title bar; the page reports the drag so the window can move itself. */
  dragStart(): void;
  dragEnd(): void;
  /** "prev" and "next" since api 11: the route before or after the open one. */
  action(name: "size" | "pin" | "close" | "prev" | "next"): void;
  /** Read by nothing since api 18: the user sizes the plaque, and the page fits its rows. */
  setHeight(height: number): void;
  /** Where a pinned, click-through plaque should still receive the mouse. */
  setHotspot(x: number, y: number, w: number, h: number): void;
}

export interface StepsSignals {
  dataChanged: QtSignal;
}

export type StepsObject = StepsSlots & StepsSignals;
