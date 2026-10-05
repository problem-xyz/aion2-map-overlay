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
  /**
   * Since api 27: whether the overlay follows the route. Off, it draws the cubes and resources of
   * whichever map is open, found by itself, and no route, checklist or off-route hint.
   */
  route_mode: boolean;
  /** Since api 27: far off the route, the hint over the map and the offer to go on from later. */
  route_far_notice: boolean;
  route_ahead: number;
  route_past: number;
  /**
   * Since api 23: the map's hidden cubes over the game, every one whatever the route's progress,
   * each in a ring `cube_radius` screen pixels across its middle (0 draws the cube alone).
   * `overlayVisible` no longer takes them away: it is the route's switch alone.
   */
  show_cubes: boolean;
  cube_radius: number;
  /**
   * Since api 24: the route's points on Empyrean Traces, the feathers. Off leaves them out of the
   * overlay, the checklist and `progress`, which then counts and lists only the points shown.
   */
  route_traces: boolean;
  /** Since api 25: the same for the route's points on sealed dungeons. */
  route_seals: boolean;
  /**
   * Since api 26: the map's gathering points over the game, of the resources `resources` lists
   * (ids from assets/marks/resources.json). The list is kept while the switch is off.
   */
  show_resources: boolean;
  resources: string[];
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
  /**
   * Since api 28, the timers. The server region by its id in the schedule; "" works it out from
   * the clock's offset (TimersState.regionGuessed). The server group narrows a Korean region's
   * siege to one of its start times; "" for all of them.
   */
  timers_region: string;
  timers_server_group: string;
  timers_clock_12h: boolean;
  timers_sound: boolean;
  timers_volume: number;
  /** Fetch newer schedules and boss readings from the repository. */
  timers_fetch: boolean;
  /** Each event's own choices by its id; missing keys take the defaults for its kind. */
  timers_events: Record<string, Partial<TimerChoice>>;
  timers_world_shown: string[];
  timers_world_lead: number;
  timers_world_signal: TimerSignal;
  timers_plaque_pinned: boolean;
  timers_plaque_scale: number;
  timers_plaque_filter: "all" | "event" | "boss";
  timers_plaque_collapsed: boolean;
}

/** How a reminder sounds: a spoken phrase, or a chime. */
export type TimerSignal = "voice" | "chime";

/** What the user chose for one event, over the defaults for its kind. */
export interface TimerChoice {
  /** On the plaque. */
  shown: boolean;
  /** Minutes ahead the reminder sounds: 0, 2, 5, 10 or 15; 0 is none. */
  lead: number;
  signal: TimerSignal;
}

/** A span of an event, in epoch milliseconds. */
export interface TimerSpan {
  start: number;
  end: number;
}

/** One event as getState().timers lists it: what it is, the user's choices, and its moments. */
export interface TimerEvent extends TimerChoice {
  id: string;
  /** As the game client spells it; never translated. */
  name: string;
  kind: "event" | "boss" | "reset";
  realm: "abyss" | "world" | null;
  /** A mark of shared/ui/timerMarks.ts; an unknown one draws a neutral token. */
  icon: string;
  /** 0 for a moment, such as a reset, rather than a span. */
  durationMin: number;
  /** How long entry stays open after the start; 0 for no such phase. */
  entryMin: number;
  live: TimerSpan | null;
  /** While entry is still open, when it closes. */
  entryCloses: number | null;
  /** null only for a one-off event that has passed. */
  next: (TimerSpan & { group: string | null }) | null;
  /** Every occurrence from two hours back to two days ahead, as [start, end]. */
  occurrences: [number, number][];
  /** A weekly event's starts over the coming week, to read its days off; empty otherwise. Api 30. */
  weekStarts?: number[];
}

/** A world boss: one spawn read off the game's list, and the cycles after it estimated. */
export interface WorldBossTimer {
  id: string;
  name: string;
  /** Where on the map it spawns. */
  area: string;
  level: number;
  respawnS: number;
  /** On the plaque. */
  shown: boolean;
  /** Its current spawn while up, else the next one. */
  spawn: number;
  up: boolean;
  /** Worked out past the reading: spawn, a kill of about 90 s, the cycle. */
  estimated: boolean;
  /** Every spawn from two hours back to two days ahead. */
  spawns: number[];
}

/** getState().timers since api 28; null when no schedule could be loaded at all. */
export interface TimersState {
  /** When Python worked this out; a page counts on from its own clock. */
  now: number;
  region: string;
  regionGuessed: boolean;
  regions: { id: string; label: string; group: string }[];
  /** The region's server groups; empty for most. */
  serverGroups: string[];
  serverGroup: string | null;
  /** The schedule's date. */
  updatedAt: string;
  fetching: boolean;
  events: TimerEvent[];
  /** Empty when the reading is from another region than the one shown. */
  bosses: WorldBossTimer[];
  bossesReadAt: number | null;
  bossesMap: string | null;
  /** Bosses whose reading said more time left than their cycle: the cycle in the file is wrong. */
  wrongCycle: string[];
}

/**
 * One setting as `settings_schema()` in core/settings.py describes it.
 *
 * `min`/`max` are the range Python clamps every value to, on load and on every updateSettings, so
 * a control that reads them offers exactly what the file accepts. They exist only on a ranged
 * field, and `choices` only on one with a fixed list.
 */
export interface SettingSchema {
  /** "list" since api 26: a list of strings, `resources`. "map" since api 28: `timers_events`. */
  type: "bool" | "int" | "float" | "str" | "list" | "map";
  default: boolean | number | string | string[] | Record<string, unknown>;
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
  /** Since api 26: the gathering resources its sets have points of, in the order to list them. */
  resources?: string[];
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
  /** The timers, as `timersChanged` also carries them. Absent before api 28. */
  timers?: TimersState | null;
  /** The timers plaque over the game. Absent before api 31. */
  timersPlaque?: { visible: boolean; pinned: boolean };
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

  // timers (api 28)
  /** JSON Partial<TimerChoice>, merged over the event's earlier choices. */
  setTimerEvent(eventId: string, payload: string): void;
  /** JSON list of world-boss ids, the ones on the plaque. */
  setTimersWorldShown(payload: string): void;
  /** Fetch the schedule and the world bosses now. */
  refreshTimersData(): void;
  /** Play the event's (or world boss's) reminder at the volume set; "" plays the chime. Api 29. */
  previewTimerSignal(eventId: string): void;
  /** The timers plaque over the game, up or down. Api 31. */
  setTimersPlaqueVisible(visible: boolean): void;
  setTimersPlaquePinned(pinned: boolean): void;
  /** The day timeline in a window of its own; a second call raises it. Api 32. */
  openTimersTimeline(): void;
  closeTimersTimeline(): void;
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
  /** JSON TimersState (or null) when what it says changes. Api 28. */
  timersChanged: QtSignal;
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

/** What the timers plaque draws, from qt/timers_window.py. Api 31. */
export interface TimersPlaqueData {
  timers: TimersState | null;
  filter: "all" | "event" | "boss";
  clock12h: boolean;
  /** The world bosses' common reminder lead, for the plaque's bell. */
  worldLead: number;
  /** Folded up to its head: the nearest timer alone. */
  collapsed: boolean;
  /** The reminder last sounded, marked on its row until its event starts. */
  ring: { id: string; name: string; start: number; boss: boolean } | null;
  scale: number;
  pinned: boolean;
  opacity: number;
  grip: number;
  language: string;
}

/** The `timers` object the timers plaque talks to: the steps plaque's, but for `setHeight`. */
export interface TimersPlaqueSlots {
  getData(cb: (json: string) => void): void;
  dragStart(): void;
  dragEnd(): void;
  /** "pin", "collapse", "close", "filter:all", "filter:event" or "filter:boss". */
  action(name: string): void;
  setHotspot(x: number, y: number, w: number, h: number): void;
}

export type TimersPlaqueObject = TimersPlaqueSlots & StepsSignals;
