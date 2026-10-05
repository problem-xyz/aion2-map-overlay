/**
 * getState().timers for the mock backend, worked out here from the files Python reads.
 *
 * The app works these out in timers/view.py; this is the mock standing in for it so the timers
 * pages can be built in a browser. It follows the same rules -- a rule's times on its own zone or
 * its region's, a world boss's next spawn its read one plus 90 s plus its cycle -- closely enough
 * for a page, and is never what the app shows.
 */

import type { Settings, TimerEvent, TimersState, WorldBossTimer } from "@/shared/backend/contract";

import scheduleDoc from "../../../assets/timers/schedule.json";
import bossDoc from "../../../assets/timers/world-bosses.json";

interface Rule {
  type: "hourly" | "daily" | "weekly" | "once";
  minute?: number;
  times?: string[];
  days?: string[];
  timeZone?: string;
  at?: string;
  groups?: string[];
}

const HOUR = 3_600_000;
const MIN = 60_000;
const BEFORE = 2 * HOUR;
const AFTER = 48 * HOUR;
const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const KILL = 90_000;
const UP = 3 * MIN;

const formats = new Map<string, Intl.DateTimeFormat>();

/** The wall clock in a zone at a moment: its date parts and weekday. */
function wall(ts: number, zone: string) {
  let f = formats.get(zone);
  if (!f) {
    f = new Intl.DateTimeFormat("en-US", {
      timeZone: zone,
      hourCycle: "h23",
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
    formats.set(zone, f);
  }
  const p: Record<string, number> = {};
  for (const part of f.formatToParts(ts)) if (part.type !== "literal") p[part.type] = +part.value;
  return {
    y: p.year ?? 0,
    m: p.month ?? 1,
    d: p.day ?? 1,
    h: p.hour ?? 0,
    mi: p.minute ?? 0,
    s: p.second ?? 0,
  };
}

/** A wall-clock time in a zone, as epoch milliseconds. */
function zoned(y: number, m: number, d: number, h: number, mi: number, zone: string): number {
  const guess = Date.UTC(y, m - 1, d, h, mi);
  const offsetAt = (ts: number) => {
    const w = wall(ts, zone);
    return Date.UTC(w.y, w.m - 1, w.d, w.h, w.mi, w.s) - Math.floor(ts / 1000) * 1000;
  };
  return guess - offsetAt(guess - offsetAt(guess));
}

function starts(rule: Rule, zone: string, from: number, to: number): [number, string | null][] {
  if (rule.type === "once") return rule.at ? [[Date.parse(rule.at), null]] : [];
  const tz = rule.timeZone ?? zone;
  const first = wall(from - 24 * HOUR, tz);
  const out: [number, string | null][] = [];
  for (let k = 0; k < 10; k += 1) {
    const day = new Date(Date.UTC(first.y, first.m - 1, first.d + k));
    const [y, m, d] = [day.getUTCFullYear(), day.getUTCMonth() + 1, day.getUTCDate()];
    if (rule.type === "hourly") {
      for (let h = 0; h < 24; h += 1) out.push([zoned(y, m, d, h, rule.minute ?? 0, tz), null]);
      continue;
    }
    if (rule.type === "weekly" && !rule.days?.includes(DAYS[day.getUTCDay()] ?? "")) continue;
    (rule.times ?? []).forEach((t, i) => {
      const [h, mi] = t.split(":").map(Number);
      out.push([zoned(y, m, d, h ?? 0, mi ?? 0, tz), rule.groups?.[i] ?? null]);
    });
  }
  return out.filter(([s]) => s < to + 24 * HOUR).sort((a, b) => a[0] - b[0]);
}

function choiceOf(settings: Settings, id: string, kind: string) {
  const defaults = { shown: true, lead: kind === "reset" ? 0 : 5, signal: "chime" as const };
  return { ...defaults, ...settings.timers_events[id] };
}

function eventOf(
  e: (typeof scheduleDoc.events)[number],
  region: (typeof scheduleDoc.regions)[number],
  now: number,
  group: string | null,
  settings: Settings,
): TimerEvent | null {
  const rules = e.schedules as Record<string, Rule | undefined>;
  const rule = rules[region.id] ?? rules[region.group];
  if (!rule) return null;
  const span = ("durationMinutes" in e ? (e.durationMinutes as number) : 0) * MIN;
  const entry = "entryMinutes" in e ? (e.entryMinutes as number) : 0;
  const all = starts(rule, region.timeZone, now - BEFORE - span, now + 8 * 24 * HOUR)
    .filter(([, g]) => !group || !g || g === group)
    .map(([s, g]) => ({ start: s, end: s + span, group: g }));
  const live = all.find((o) => o.start <= now && now < o.end) ?? null;
  const next = all.find((o) => o.start > now) ?? null;
  const closes = live && entry ? live.start + entry * MIN : null;
  return {
    id: e.id,
    name: e.name,
    kind: e.kind as TimerEvent["kind"],
    realm: ("realm" in e ? e.realm : null) as TimerEvent["realm"],
    icon: e.icon,
    durationMin: span / MIN,
    entryMin: entry,
    ...choiceOf(settings, e.id, e.kind),
    live: live ? { start: live.start, end: live.end } : null,
    entryCloses: closes && now < closes ? closes : null,
    next,
    occurrences: all
      .filter(
        (o) => o.start < now + AFTER && (span ? o.end > now - BEFORE : o.start >= now - BEFORE),
      )
      .map((o) => [o.start, o.end] as [number, number]),
    weekStarts:
      rule.type === "weekly"
        ? all.filter((o) => o.start >= now && o.start < now + 7 * 24 * HOUR).map((o) => o.start)
        : [],
  };
}

function seconds(text = ""): number {
  let out = 0;
  for (const [, n, unit] of text.matchAll(/(\d+)\s*(h|min|m|s)/g)) {
    out += Number(n) * (unit === "h" ? 3600 : unit === "s" ? 1 : 60);
  }
  return out;
}

function bossOf(
  b: (typeof bossDoc.bosses)[number],
  readAt: number,
  now: number,
  shown: string[],
): WorldBossTimer {
  const respawn = seconds(b.respawn) * 1000;
  // a boss missing from the last reading keeps the spawn the one before projected for it
  const first =
    "spawnsAt" in b && b.spawnsAt
      ? Date.parse(b.spawnsAt)
      : readAt + seconds("timeLeft" in b ? b.timeLeft : undefined) * 1000;
  const cycle = KILL + respawn;
  let spawn = first;
  if (first + UP <= now) spawn += cycle * (Math.floor((now - UP - first) / cycle) + 1);
  const spawns: number[] = [];
  let s = first + cycle * Math.max(0, Math.floor((now - BEFORE - UP - first) / cycle) + 1);
  if (first + UP > now - BEFORE) s = first;
  for (; s < now + AFTER; s += cycle) spawns.push(s);
  return {
    id: b.id,
    name: b.name,
    area: b.area,
    level: b.level,
    respawnS: respawn / 1000,
    drops: "drops" in b && Array.isArray(b.drops) ? b.drops : [],
    shown: shown.includes(b.id),
    spawn,
    up: spawn <= now && now < spawn + UP,
    estimated: spawn !== first,
    spawns,
  };
}

/** The mock's timers at `now`, for the settings given. */
export function makeTimers(settings: Settings, now: number, fetching = false): TimersState {
  const regions = scheduleDoc.regions;
  const chosen = regions.find((r) => r.id === settings.timers_region);
  const region = chosen ?? regions.find((r) => r.id === "global-eu") ?? regions[0]!;
  const groups = [
    ...new Set(
      scheduleDoc.events.flatMap((e) => {
        const rules = e.schedules as Record<string, Rule | undefined>;
        return (rules[region.id] ?? rules[region.group])?.groups ?? [];
      }),
    ),
  ];
  const group = groups.includes(settings.timers_server_group) ? settings.timers_server_group : null;
  const here = bossDoc.region === region.id;
  const readAt = Date.parse(bossDoc.readAt);
  return {
    now,
    region: region.id,
    regionGuessed: !chosen,
    regions: regions.map((r) => ({ id: r.id, label: r.label, group: r.group })),
    serverGroups: groups,
    serverGroup: group,
    updatedAt: scheduleDoc.updatedAt,
    fetching,
    events: scheduleDoc.events
      .map((e) => eventOf(e, region, now, group, settings))
      .filter((e): e is TimerEvent => e !== null),
    bosses: here
      ? bossDoc.bosses.map((b) => bossOf(b, readAt, now, settings.timers_world_shown))
      : [],
    bossesReadAt: here ? readAt : null,
    bossesMap: here ? bossDoc.map : null,
    wrongCycle: [],
  };
}
