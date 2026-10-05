/**
 * Named states for the mock backend, picked from the address: `?mock=1&scenario=many#editor`.
 *
 * A design review looks at each screen in the states that break it, and building those by
 * hand in the console every time is how states get skipped. A scenario rewrites the seed state
 * once, at boot; after that the mock behaves as usual, so everything stays clickable.
 *
 *   scenario=typical   three routes, both maps, a map area (the default)
 *   scenario=empty     no routes, no map area, both maps still being cut into tiles
 *   scenario=many      25 routes with long names; the current one has 96 points
 *   scenario=errors    a toast of every level, and a route whose map this version lacks
 *   scenario=progress  96 points, 7 of them done
 *   scenario=update    the update banner; pick the phase with update=<phase>
 *   scenario=steps     the steps plaque; steps=0|1|12|100 points, long=1 for 120-char labels
 *   scenario=editor    96 points on Altgard; tiles=busy shows the map still being cut
 *
 * Parameters that apply to any scenario: update=<phase>, size=s|m|l, pinned=0|1, lang=en|ru,
 * markers=<n> (the current route's length), bg=1|<name> (a game screenshot behind the page).
 *
 * Real map tiles and object sets are used when they are on this machine: the tiles the app cut
 * into userdata/ on its first run, and the sets in assets/object-sets/. Game screenshots come
 * from docs/design/reference/, a local, git-ignored folder that only ever holds your own
 * captures -- they are read from disk here and never copied into the tree.
 */

import type {
  AppState,
  ObjectSet,
  RouteDoc,
  RouteInfo,
  StepsSize,
  UpdatePhase,
} from "@/shared/backend/contract";

import { MOCK_UPDATE } from "./mockState";

export type ScenarioName =
  "typical" | "empty" | "many" | "errors" | "progress" | "update" | "steps" | "editor";

const SCENARIOS: readonly ScenarioName[] = [
  "typical",
  "empty",
  "many",
  "errors",
  "progress",
  "update",
  "steps",
  "editor",
];

const PHASES: readonly UpdatePhase[] = [
  "disabled",
  "idle",
  "checking",
  "none",
  "available",
  "downloading",
  "ready",
  "failed",
];

export interface Scenario {
  name: ScenarioName;
  update: UpdatePhase | null;
  steps: number | null;
  long: boolean;
  size: StepsSize | null;
  pinned: boolean | null;
  lang: "en" | "ru" | null;
  markers: number | null;
  tilesBusy: boolean;
  bg: string | null;
  /** Minutes the timers' clock is moved by, either way, to show an event running or a boss up. */
  shift: number;
}

function pick<T extends string>(value: string | null, allowed: readonly T[]): T | null {
  return value !== null && (allowed as readonly string[]).includes(value) ? (value as T) : null;
}

function count(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) return null;
  return Math.min(Number(value), 500);
}

function flag(value: string | null): boolean | null {
  if (value === null) return null;
  return value === "1" || value === "true";
}

export function readScenario(search: string): Scenario {
  const q = new URLSearchParams(search);
  return {
    name: pick(q.get("scenario"), SCENARIOS) ?? "typical",
    update: pick(q.get("update"), PHASES),
    steps: count(q.get("steps")),
    long: flag(q.get("long")) ?? false,
    size: pick(q.get("size"), ["s", "m", "l"] as const),
    pinned: flag(q.get("pinned")),
    lang: pick(q.get("lang"), ["en", "ru"] as const),
    markers: count(q.get("markers")),
    tilesBusy: q.get("tiles") === "busy",
    bg: q.get("bg"),
    shift: /^-?\d{1,5}$/.test(q.get("shift") ?? "") ? Number(q.get("shift")) : 0,
  };
}

// ------------------------------------------------------------------ building blocks

const LABELS = [
  "Talk to the quest giver",
  "",
  "Empyrean Trace",
  "Kill the named elite by the northern bridge",
  "",
  "Gather Azphel's Lily",
  "Teleport to Black Claw Outpost",
  "Hidden Cube behind the waterfall",
];

const LONG_LABEL =
  "Follow the river bank east past the second watchtower, then climb the ridge to the shrine " +
  "and talk to the old keeper there";

function makeMarkers(n: number, long: boolean): RouteDoc["markers"] {
  // A serpentine over the middle of a 4096 map, so a long route stays on screen and in order
  const perRow = 12;
  return Array.from({ length: n }, (_, i) => {
    const row = Math.floor(i / perRow);
    const col = row % 2 === 0 ? i % perRow : perRow - 1 - (i % perRow);
    const text = long ? LONG_LABEL : (LABELS[i % LABELS.length] ?? "");
    return {
      x: 700 + col * 230,
      y: 600 + row * 330,
      text: text && !long ? `${text} ${i + 1}` : text,
      ...(i % 17 === 5 ? { color: "#6ea8ff" } : {}),
    };
  });
}

function swatch(label: string): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180">` +
    `<rect width="320" height="180" fill="#242a36"/>` +
    `<text x="160" y="96" font-family="sans-serif" font-size="18" fill="#e7eaf1" ` +
    `text-anchor="middle">${label.slice(0, 24)}</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

const LONG_NAMES = [
  "Altgard: from the Observatory to Black Claw, every Empyrean Trace on the way",
  "Daily loop",
  "Verteron gathering run (lilies, ore, and the two hidden cubes near the lake)",
  "Level 20-25 story quests, Altgard west",
  "Seals",
];

function manyRoutes(): RouteInfo[] {
  return Array.from({ length: 25 }, (_, i) => {
    const base = LONG_NAMES[i % LONG_NAMES.length] ?? "Route";
    const label = i < LONG_NAMES.length ? base : `${base} ${i + 1}`;
    const onAltgard = i % 3 !== 1;
    return {
      id: `route-${i + 1}`,
      label,
      map: onAltgard ? "altgard" : "verteron",
      mapLabel: onAltgard ? "Altgard" : "Verteron",
      markers: 5 + ((i * 7) % 90),
      steps: (i * 3) % 12,
      thumb: swatch(label),
    };
  });
}

/** Points the route is made of, set into the editor document and the progress in one go. */
function setRoute(state: AppState, doc: RouteDoc, markers: RouteDoc["markers"], done: number) {
  doc.markers = markers;
  doc.mapSize = [4096, 4096];
  doc.map = "altgard";
  state.progress = {
    done: Math.min(done, markers.length),
    total: markers.length,
    map: [4096, 4096],
    markers: markers.map((m, i) => ({
      n: i + 1,
      text: m.text,
      color: m.color ?? doc.style.color,
      x: m.x,
      y: m.y,
      ...(m.icon ? { icon: m.icon } : {}),
    })),
  };
  const current = state.routes.find((r) => r.id === state.route);
  if (current) current.markers = markers.length;
}

function setUpdatePhase(state: AppState, phase: UpdatePhase) {
  const known = { version: MOCK_UPDATE.version, notes: MOCK_UPDATE.notes, skipped: false };
  switch (phase) {
    case "available":
    case "ready":
      state.update = { phase, ...known };
      break;
    case "downloading":
      state.update = { phase, ...known, progress: 40 };
      break;
    case "failed":
      state.update = {
        phase,
        ...known,
        stage: "download",
        code: "update.failed",
        reason: "the connection was reset",
      };
      break;
    default:
      state.update = { phase };
  }
}

// ------------------------------------------------------------------ applying

/**
 * Rewrites the freshly booted state and editor document for the scenario. Synchronous and
 * done before the first `getState`, so the page never renders the default state first.
 */
export function applyScenario(state: AppState, doc: RouteDoc, s: Scenario): void {
  switch (s.name) {
    case "empty":
      state.routes = [];
      state.route = null;
      state.region = null;
      state.progress = { done: 0, total: 0, map: null, markers: [] };
      for (const m of state.maps) m.tiles = { ...m.tiles, ready: false };
      state.tilesBusy = state.maps.map((m) => m.id);
      doc.markers = [];
      break;
    case "many":
      state.routes = manyRoutes();
      state.route = "route-1";
      setRoute(state, doc, makeMarkers(96, false), 0);
      break;
    case "errors":
      state.routes.push({
        id: "old-map",
        label: "Route on a map this version does not have",
        map: "elyos-old",
        mapLabel: "",
        markers: 14,
        steps: 0,
        thumb: swatch("Missing map"),
      });
      break;
    case "progress":
      setRoute(state, doc, makeMarkers(96, false), 7);
      break;
    case "update":
      setUpdatePhase(state, s.update ?? "available");
      break;
    case "steps":
      // one point at least is left to walk: with every point done the plaque hides itself, and
      // steps=1 showed nothing at all
      setRoute(
        state,
        doc,
        makeMarkers(s.steps ?? 12, s.long),
        Math.min(3, Math.max(0, (s.steps ?? 12) - 1)),
      );
      break;
    case "editor":
      setRoute(state, doc, makeMarkers(s.markers ?? 96, false), 0);
      break;
    case "typical":
      state.routes.push({
        id: "daily",
        label: "Daily loop",
        map: "altgard",
        mapLabel: "Altgard",
        markers: 9,
        steps: 4,
        thumb: swatch("Daily loop"),
      });
      break;
  }

  if (s.markers !== null && s.name !== "editor")
    setRoute(state, doc, makeMarkers(s.markers, s.long), 0);
  if (s.update && s.name !== "update") setUpdatePhase(state, s.update);
  if (s.size) {
    state.steps.size = s.size;
    state.settings.steps_size = s.size;
    state.settings.steps_scale = { s: 0.5, m: 0.5, l: 0.86 }[s.size];
  }
  if (s.pinned !== null) {
    state.steps.pinned = s.pinned;
    state.settings.steps_pinned = s.pinned;
  }
  if (s.lang) state.settings.language = s.lang;
  if (s.tilesBusy) {
    for (const m of state.maps) m.tiles = { ...m.tiles, ready: false };
    state.tilesBusy = state.maps.map((m) => m.id);
  }
}

/** The toasts of the `errors` scenario, one per level, sent once the page listens. */
export function scenarioNotices(s: Scenario) {
  if (s.name !== "errors") return [];
  return [
    {
      level: "info",
      code: "route.saved",
      params: { name: "Altgard loop" },
      text: "Route “Altgard loop” saved.",
    },
    {
      level: "warning",
      code: "overlay.capture_visible_on",
      text: "The overlay is now visible in screen recordings.",
    },
    {
      level: "error",
      code: "share.not_a_code",
      text: "That is not a route code for this app.",
    },
    {
      level: "error",
      code: "update.failed",
      params: { reason: "the connection was reset" },
      text: "The update failed: the connection was reset",
    },
  ] as const;
}

// ------------------------------------------------------------------ local files

/** The object sets in assets/object-sets, turned into what getObjects answers with. */
const SET_FILES = import.meta.glob<{
  mapName?: string;
  categories?: { id: string; name?: string; parentId?: string | null; color?: string }[];
  nodes?: { categoryId: string; x: number; y: number; title?: string; description?: string }[];
}>("../../../assets/object-sets/*.json", { import: "default" });

export async function loadObjectSets(mapId: string): Promise<ObjectSet[] | null> {
  const entry = Object.entries(SET_FILES).find(([path]) => path.endsWith(`/${mapId}.json`));
  if (!entry) return null;
  const raw = await entry[1]();
  return [
    {
      file: `bundled/${mapId}.json`,
      mapName: raw.mapName ?? mapId,
      bundled: true,
      categories: (raw.categories ?? []).map((c) => ({
        id: c.id,
        name: c.name ?? c.id,
        parentId: c.parentId ?? null,
        color: c.color ?? "#8f99ad",
      })),
      nodes: (raw.nodes ?? []).map((n) => ({
        c: n.categoryId,
        x: n.x,
        y: n.y,
        t: n.title ?? "",
        d: n.description ?? "",
      })),
    },
  ];
}

/** Where the app cut a map's tiles on this machine and how deep, or null if it never has. */
export async function localTiles(mapId: string): Promise<{ url: string; zMax: number } | null> {
  // Read here rather than at module level: the define exists under Vite, not under Vitest
  const url = `${__MOCK_USERDATA__}/maps/${mapId}/tiles`;
  try {
    const res = await fetch(`${url}/done.json`);
    // Vite answers a missing /@fs/ file with the index page, so the type is what tells
    if (!res.ok || !(res.headers.get("content-type") ?? "").includes("json")) return null;
    const done = (await res.json()) as { zMax?: number };
    return { url, zMax: done.zMax ?? 4 };
  } catch {
    return null;
  }
}

const REFERENCES = import.meta.glob<string>("../../../docs/design/reference/*.png", {
  query: "?url",
  import: "default",
});

/** A game screenshot for `bg=`: `1` the first one, anything else a part of its file name. */
export async function referenceImage(bg: string | null): Promise<string | null> {
  if (!bg) return null;
  const files = Object.keys(REFERENCES).sort();
  const path =
    bg === "1" ? files[0] : files.find((f) => f.toLowerCase().includes(bg.toLowerCase()));
  const load = path ? REFERENCES[path] : undefined;
  return load ? load() : null;
}
