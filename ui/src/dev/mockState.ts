/**
 * Seed data for the mock backend.
 *
 * Shaped exactly like what Python sends, because the whole point is that the UI cannot tell
 * the difference. Thumbnails are tiny inline SVGs rather than real screenshots so this file
 * stays readable and the dev bundle stays small.
 */

import type {
  AppState,
  ObjectSet,
  RouteDoc,
  SettingSchema,
  Settings,
  StepsData,
} from "@/shared/backend/contract";
import type { ObjectIconName } from "@/shared/ui/markIcons";

function swatch(color: string, label: string, width = 320, height = 180): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
    `<rect width="${width}" height="${height}" fill="${color}"/>` +
    `<text x="${width / 2}" y="${height / 2 + 6}" font-family="sans-serif" font-size="20" ` +
    `fill="#e7eaf1" text-anchor="middle">${label}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

export const MOCK_ROUTE: RouteDoc = {
  format: "map-overlay-route",
  version: 1,
  name: "Altgard loop",
  map: "altgard",
  mapSize: [8192, 8192],
  markers: [
    { x: 1200, y: 2400, text: "Pick up the quest", color: "#f2b544", icon: "main" },
    // on a teleport, an Empyrean Trace and a seal of assets/object-sets/altgard.json, so the
    // lists show the object icons
    { x: 3197.3, y: 2850.8, text: "" },
    { x: 3224.4, y: 2858.2, text: "Empyrean trace" },
    { x: 5213.4, y: 2166.8, text: "" },
    { x: 4400, y: 4200, text: "Turn in", color: "#6ea8ff" },
  ],
  style: { color: "#f2b544", width: 3 },
};

/**
 * Object sets as `getObjects` returns them: categories and every point, not the summary that
 * `getState` puts on a map. Coordinates are percentages of the map, like the real files.
 *
 * "Ore" carries the neutral colour Python assigns to a category that has none, so the editor's
 * inherit-from-parent rule is exercised here too.
 */
export const MOCK_OBJECT_SETS: Record<string, ObjectSet[]> = {
  altgard: [
    {
      file: "bundled/altgard.json",
      mapName: "Altgard",
      bundled: true,
      categories: [
        { id: "teleport", name: "Teleports", parentId: null, color: "#6ea8ff" },
        { id: "gather", name: "Gathering", parentId: null, color: "#22c55e" },
        { id: "ore", name: "Ore", parentId: "gather", color: "#8f99ad" },
      ],
      nodes: [
        { c: "teleport", x: 14.6, y: 29.3, t: "Altgard Observatory", d: "" },
        { c: "teleport", x: 47.9, y: 51.2, t: "Empyrean Trace", d: "SafeHaven" },
        { c: "teleport", x: 62.1, y: 63.4, t: "Black Claw Outpost", d: "" },
        { c: "gather", x: 25.6, y: 31.7, t: "Azphel's Lily", d: "" },
        { c: "gather", x: 37.2, y: 37.8, t: "Azphel's Lily", d: "" },
        { c: "ore", x: 53.7, y: 41.5, t: "Titanium Ore", d: "" },
        { c: "ore", x: 55.4, y: 44.9, t: "Titanium Ore", d: "" },
      ],
    },
  ],
};

/**
 * What `settings_schema()` in core/settings.py sends, copied by hand.
 *
 * This is the mock standing in for Python, not a second source of ranges for the UI: nothing in
 * src/features reads it, only the mock backend hands it out. If Python moves a range, the dev
 * mock is merely out of date until this is updated; the app itself is never wrong.
 */
export const MOCK_SETTINGS_SCHEMA: Record<keyof Settings, SettingSchema> = {
  opacity: { type: "float", default: 0.85, min: 0.1, max: 1 },
  fps: { type: "int", default: 60, min: 30, max: 240 },
  detector: { type: "str", default: "sift", choices: ["sift", "orb"] },
  detect_scale: { type: "float", default: 1, min: 0.25, max: 1 },
  min_inliers: { type: "int", default: 20, min: 8, max: 60 },
  transform: { type: "str", default: "similarity", choices: ["similarity", "homography"] },
  tracking: { type: "str", default: "flow", choices: ["flow", "detect"] },
  smoothing: { type: "float", default: 0.5, min: 0, max: 0.9 },
  detect_interval: { type: "float", default: 0.4, min: 0.1, max: 2 },
  flow_points: { type: "int", default: 200, min: 40, max: 2000 },
  hold_frames: { type: "int", default: 8, min: 0, max: 100 },
  progress_enabled: { type: "bool", default: true },
  auto_progress: { type: "bool", default: true },
  player_anchor_x: { type: "float", default: 0.5, min: 0, max: 1 },
  player_anchor_y: { type: "float", default: 0.5, min: 0, max: 1 },
  arrive_radius: { type: "float", default: 8 / 4096, min: 8 / 4096, max: 32 / 4096 },
  ratio: { type: "float", default: 0.75, min: 0.5, max: 0.95 },
  reproj_thr: { type: "float", default: 4, min: 0.5, max: 20 },
  ref_features: { type: "int", default: 100000, min: 0, max: 1000000 },
  frame_features: { type: "int", default: 2500, min: 200, max: 20000 },
  capture_visible: { type: "bool", default: false },
  steps_pinned: { type: "bool", default: true },
  steps_size: { type: "str", default: "m", choices: ["s", "m", "l"] },
  steps_scale: { type: "float", default: 1, min: 0.5, max: 1.5 },
  route_view: { type: "str", default: "steps", choices: ["steps", "dim", "all"] },
  route_ahead: { type: "int", default: 3, min: 1, max: 10 },
  route_past: { type: "int", default: 3, min: 0, max: 10 },
  show_cubes: { type: "bool", default: false },
  route_traces: { type: "bool", default: true },
  route_seals: { type: "bool", default: true },
  show_resources: { type: "bool", default: false },
  route_mode: { type: "bool", default: true },
  route_far_notice: { type: "bool", default: true },
  resources: { type: "list", default: [] },
  cube_radius: { type: "int", default: 20, min: 0, max: 100 },
  editor_route_view: { type: "str", default: "dim", choices: ["dim", "all"] },
  editor_route_ahead: { type: "int", default: 3, min: 1, max: 10 },
  editor_opacity: { type: "float", default: 1, min: 0.1, max: 1 },
  language: { type: "str", default: "auto", choices: ["auto", "en", "ru"] },
  updates_auto_check: { type: "bool", default: true },
  updates_auto_download: { type: "bool", default: true },
  updates_skipped_version: { type: "str", default: "" },
  timers_region: { type: "str", default: "" },
  timers_server_group: { type: "str", default: "" },
  timers_clock_12h: { type: "bool", default: false },
  timers_sound: { type: "bool", default: true },
  timers_volume: { type: "float", default: 0.8, min: 0, max: 1 },
  timers_fetch: { type: "bool", default: true },
  timers_events: { type: "map", default: {} },
  timers_world_shown: { type: "list", default: [] },
  timers_world_lead: { type: "int", default: 5, min: 0, max: 15 },
  timers_world_signal: { type: "str", default: "chime", choices: ["voice", "chime"] },
  timers_plaque_pinned: { type: "bool", default: true },
  timers_plaque_scale: { type: "float", default: 1, min: 0.5, max: 1.5 },
  timers_plaque_filter: { type: "str", default: "all", choices: ["all", "event", "boss"] },
  timers_plaque_collapsed: { type: "bool", default: false },
};

export function makeState(): AppState {
  return {
    version: "1.0.0-beta.0",
    api: 22,
    running: false,
    overlayVisible: true,
    captureVisible: false,
    region: { left: 2956, top: 1172, width: 866, height: 873 },
    route: "altgard-loop",
    routes: [
      {
        id: "altgard-loop",
        label: "Altgard loop",
        map: "altgard",
        mapLabel: "Altgard",
        markers: 5,
        steps: 3,
        thumb: swatch("#2b323f", "Altgard loop"),
        faction: "asmodian",
        official: true,
      },
      {
        id: "verteron-run",
        label: "Verteron run",
        map: "verteron",
        mapLabel: "Verteron",
        markers: 12,
        steps: 7,
        thumb: swatch("#343d4d", "Verteron run"),
        faction: "elyos",
        official: false,
      },
    ],
    maps: [
      {
        id: "altgard",
        label: "Altgard",
        size: [4096, 4096],
        faction: "asmodian",
        thumb: swatch("#242a36", "Altgard"),
        tiles: { ready: true, zMax: 4, tile: 256 },
        objects: [{ file: "bundled/altgard.json", mapName: "Altgard", nodes: 7, bundled: true }],
        resources: ["odyle", "orichalcum", "sapphire", "diamond", "ruby", "asvata", "azpha"],
      },
      {
        id: "verteron",
        label: "Verteron",
        size: [4096, 4096],
        faction: "elyos",
        thumb: swatch("#242a36", "Verteron"),
        tiles: { ready: false, zMax: 0, tile: 256 },
        objects: [],
        resources: [],
      },
    ],
    settings: {
      opacity: 0.85,
      fps: 60,
      detector: "sift",
      detect_scale: 1,
      min_inliers: 20,
      transform: "similarity",
      tracking: "flow",
      smoothing: 0.5,
      detect_interval: 0.4,
      flow_points: 200,
      hold_frames: 8,
      progress_enabled: true,
      auto_progress: true,
      player_anchor_x: 0.5,
      player_anchor_y: 0.5,
      arrive_radius: 8 / 4096,
      ratio: 0.75,
      reproj_thr: 4,
      ref_features: 100000,
      frame_features: 2500,
      capture_visible: false,
      steps_pinned: true,
      steps_size: "m",
      steps_scale: 1,
      route_view: "steps",
      route_ahead: 3,
      route_past: 3,
      show_cubes: false,
      route_traces: true,
      route_seals: true,
      show_resources: false,
      route_mode: true,
      route_far_notice: true,
      resources: [],
      cube_radius: 20,
      editor_route_view: "dim",
      editor_route_ahead: 3,
      editor_opacity: 1,
      language: "auto",
      updates_auto_check: true,
      updates_auto_download: true,
      updates_skipped_version: "",
      timers_region: "",
      timers_server_group: "",
      timers_clock_12h: false,
      timers_sound: true,
      timers_volume: 0.8,
      timers_fetch: true,
      timers_events: {},
      timers_world_shown: [],
      timers_world_lead: 5,
      timers_world_signal: "chime",
      timers_plaque_pinned: true,
      timers_plaque_scale: 1,
      timers_plaque_filter: "all",
      timers_plaque_collapsed: false,
    },
    captureBackend: "dxcam",
    platform: "win32",
    steps: {
      visible: true,
      region: { left: 60, top: 140, width: 430, height: 160 },
      pinned: true,
      size: "m",
    },
    progress: {
      done: 1,
      total: 5,
      map: [8192, 8192],
      // as progress_state sends them since api 11: with the place, and a quest icon if any
      markers: MOCK_ROUTE.markers.map((m, i) => ({
        n: i + 1,
        text: m.text,
        color: m.color ?? MOCK_ROUTE.style.color,
        x: m.x,
        y: m.y,
        ...(m.icon ? { icon: m.icon } : {}),
      })),
    },
    editorOpen: false,
    tilesBusy: [],
    dev: true,
    isPortable: false,
    // idle rather than the disabled a real dev run reports, so the update flow can be tried here
    update: { phase: "idle" },
    settingsSchema: structuredClone(MOCK_SETTINGS_SCHEMA),
    // Flip to false from the console to see the old-Windows warning:
    // window.__mock.patchState((s) => { s.captureExclusion = false; })
    captureExclusion: true,
    repoUrl: "https://github.com/problem-xyz/aion2-map-overlay",
    links: {
      donate: "https://buymeacoffee.com/problem_xyz",
      discord: "https://discord.gg/DV2SNF6PMh",
      partnerDiscord: "https://discord.gg/aion2global",
    },
    banner: {
      image: swatch("#1a1446", "Banner, 1048 × 200", 1048, 200),
      url: "https://www.lagofast.com/en/?cid=892126",
      label: "LagoFast",
      code: "Problem",
      discount: "30%",
    },
  };
}

/** What the mock's update check finds. */
export const MOCK_UPDATE = {
  version: "1.0.0-beta.1",
  notes: ["### Added", "", "- The app checks for updates and installs them when it closes."].join(
    "\n",
  ),
};

// What the typical route's points sit on, as Python works it out from the object sets for the
// plaque: the mock has no object lookup of its own, so it is written down for that one route.
const MOCK_ROUTE_OBJECTS: (ObjectIconName | "")[] = ["", "teleport", "trace", "seal", ""];

/** plaque_scale in core/settings.py: the factor the plaque is drawn at for the slider's value. */
function plaqueScale(setting: number): number {
  if (setting <= 1) return 1 + Math.max(0, setting - 0.5) * 0.7;
  return 1.35 + Math.min(0.5, setting - 1) * 0.5;
}

export function makeStepsData(state: AppState): StepsData {
  const typical = state.route === "altgard-loop";
  return {
    steps: state.progress.markers.map((m, i) => {
      const object = typical ? MOCK_ROUTE_OBJECTS[i] : "";
      return {
        n: m.n,
        text: m.text,
        color: m.color,
        ...(m.icon ? { icon: m.icon } : {}),
        ...(object ? { object } : {}),
      };
    }),
    done: state.progress.done,
    past: state.settings.route_past,
    title: state.routes.find((r) => r.id === state.route)?.label ?? "",
    size: state.steps.size,
    scale: plaqueScale(state.settings.steps_scale),
    language: state.settings.language === "auto" ? "en" : state.settings.language,
    pinned: state.steps.pinned,
    switch: true,
    grip: 8,
    opacity: state.settings.opacity,
  };
}
