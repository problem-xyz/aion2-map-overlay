/**
 * What each timer says at one moment, worked out on the page from the moments Python sent.
 *
 * Python sends every occurrence from two hours back to two days ahead and only sends again when
 * something changes, so the page knows what is running and what is next at any second without
 * asking. A world boss past its spawns comes from the same list. All times are epoch ms.
 */

import type { TimerEvent, TimersState, WorldBossTimer } from "@/shared/backend/contract";

const HOUR = 3_600_000;
const MIN = 60_000;
/** How long a world boss counts as up after it spawns, as in timers/schedule.py. */
export const BOSS_UP = 3 * MIN;

export type Filter = "all" | "event" | "boss";
export type Realm = "all" | "world" | "abyss";

export interface TimerNow {
  /** "event" for a scheduled one (a reset included), "boss" for a world boss. */
  source: "event" | "boss";
  id: string;
  name: string;
  icon: string;
  kind: TimerEvent["kind"];
  realm: TimerEvent["realm"] | "world";
  /** Running now: entry open, under way, or a boss up. */
  live: { start: number; end: number; entryCloses: number | null } | null;
  /** The next start after now; null for a one-off that has passed. */
  next: number | null;
  /** Its end, when it has a span. */
  nextEnd: number | null;
  /** The moment the countdown runs to: the live one's end (or entry), else the next start. */
  target: number | null;
  /** For a world boss: the next spawn was worked out past the game's reading. */
  estimated: boolean;
  shown: boolean;
  lead: number;
  event?: TimerEvent;
  boss?: WorldBossTimer;
}

export function eventNow(e: TimerEvent, now: number): TimerNow {
  const spans = e.occurrences;
  const running = e.durationMin > 0 ? spans.find(([s, end]) => s <= now && now < end) : undefined;
  const upcoming = spans.find(([s]) => s > now);
  const fallback = e.next && e.next.start > now ? e.next : null;
  const nextStart = upcoming ? upcoming[0] : (fallback?.start ?? null);
  const nextEnd = upcoming ? upcoming[1] : (fallback?.end ?? null);
  let live: TimerNow["live"] = null;
  if (running) {
    const closes = e.entryMin > 0 ? running[0] + e.entryMin * MIN : null;
    // past its entry, a rift is under way but closed to the player: shown as what comes next
    if (closes === null || now < closes) {
      live = { start: running[0], end: running[1], entryCloses: closes };
    }
  }
  return {
    source: "event",
    id: e.id,
    name: e.name,
    icon: e.icon,
    kind: e.kind,
    realm: e.realm,
    live,
    next: nextStart,
    nextEnd,
    target: live ? (live.entryCloses ?? live.end) : nextStart,
    estimated: false,
    shown: e.shown,
    lead: e.lead,
    event: e,
  };
}

export function bossNow(b: WorldBossTimer, now: number, lead: number): TimerNow {
  const up = b.spawns.find((s) => s <= now && now < s + BOSS_UP);
  const next = b.spawns.find((s) => s > now) ?? (b.spawn > now ? b.spawn : null);
  // While Python's spawn was not estimated it is the one the game's list gave; every spawn after
  // it is worked out from the cycle.
  const read = b.estimated ? null : b.spawn;
  const estimated = next !== null && next !== read;
  return {
    source: "boss",
    id: b.id,
    name: b.name,
    icon: "demon",
    kind: "boss",
    realm: "world",
    live: up !== undefined ? { start: up, end: up + BOSS_UP, entryCloses: null } : null,
    next,
    nextEnd: null,
    target: up !== undefined ? up + BOSS_UP : next,
    estimated,
    shown: b.shown,
    lead,
    boss: b,
  };
}

/** The order the list and the plaque take: what is running first, then by the start to come. */
export function byTime(a: TimerNow, b: TimerNow): number {
  const key = (x: TimerNow) => (x.live ? -1 : (x.next ?? Number.MAX_SAFE_INTEGER));
  return key(a) - key(b);
}

export function passes(t: TimerNow, filter: Filter, realm: Realm): boolean {
  if (filter === "all") return true;
  if (filter === "event") return t.kind !== "boss";
  return t.kind === "boss" && (realm === "all" || t.realm === realm);
}

/** Every timer the state names, at now: the scheduled events, then the world bosses. */
export function timersAt(state: TimersState, now: number, worldLead: number): TimerNow[] {
  return [
    ...state.events.map((e) => eventNow(e, now)),
    ...state.bosses.map((b) => bossNow(b, now, worldLead)),
  ];
}

/** Within the reminder window, ahead of a start: what the plaque marks with its bell. */
export function soon(t: TimerNow, now: number): boolean {
  return !t.live && t.next !== null && t.lead > 0 && t.next - now <= t.lead * MIN;
}

/** Far enough off to be read more quietly: more than an hour. */
export function far(t: TimerNow, now: number): boolean {
  return !t.live && t.next !== null && t.next - now > HOUR;
}
