/**
 * Where everything sits on the day timeline: the span it covers, a lane per timer with its bars,
 * the resets across all lanes, and the hour ticks. Positions are fractions of the span, 0 to 1,
 * so the page lays them out with percentages and a resize costs nothing. All times are epoch ms.
 */

import { BOSS_UP, type Filter, passes, type Realm, type TimerNow } from "./model";

const MIN = 60_000;
const HOUR = 60 * MIN;

export type Hours = 24 | 48;

export interface Span {
  start: number;
  end: number;
}

/** From the top of the hour before now, so what has just ended is still in view. */
export function timelineSpan(now: number, hours: Hours): Span {
  const top = new Date(now);
  top.setMinutes(0, 0, 0);
  const start = top.getTime() - HOUR;
  return { start, end: start + hours * HOUR };
}

export function at(ms: number, span: Span): number {
  return (ms - span.start) / (span.end - span.start);
}

export interface Bar {
  start: number;
  end: number;
  /** Fractions of the span, clipped to it. */
  left: number;
  width: number;
  state: "past" | "live" | "ahead";
  /** A moment with no length of its own, drawn as a mark rather than a bar. */
  point: boolean;
  /** A world boss's spawn worked out from its cycle, not read in the game. */
  estimated: boolean;
}

export interface Lane {
  timer: TimerNow;
  group: "event" | "abyss" | "world";
  bars: Bar[];
}

function bar(start: number, end: number, now: number, span: Span, estimated: boolean): Bar | null {
  if (end < span.start || start > span.end) return null;
  const left = Math.max(0, at(start, span));
  const right = Math.min(1, at(end, span));
  return {
    start,
    end,
    left,
    width: Math.max(0, right - left),
    state: end <= now ? "past" : start <= now ? "live" : "ahead",
    point: end === start,
    estimated,
  };
}

function bars(timer: TimerNow, now: number, span: Span): Bar[] {
  const out: (Bar | null)[] = [];
  if (timer.event) {
    for (const [s, e] of timer.event.occurrences) out.push(bar(s, e, now, span, false));
  } else if (timer.boss) {
    const read = timer.boss.estimated ? null : timer.boss.spawn;
    for (const s of timer.boss.spawns) out.push(bar(s, s + BOSS_UP, now, span, s !== read));
  }
  return out.filter((b): b is Bar => b !== null);
}

function group(timer: TimerNow): Lane["group"] {
  if (timer.kind !== "boss") return "event";
  return timer.realm === "abyss" ? "abyss" : "world";
}

const ORDER: readonly Lane["group"][] = ["event", "abyss", "world"];

/**
 * A lane per timer the filter lets through, events first, then the Abyss's bosses, then the
 * world's, each group in the schedule's own order: lanes that kept moving as times came round
 * would be hard to follow. The resets are not lanes; see `resets`.
 */
export function lanes(
  timers: TimerNow[],
  now: number,
  span: Span,
  filter: Filter,
  realm: Realm,
): Lane[] {
  const kept = timers
    .filter((t) => t.kind !== "reset" && passes(t, filter, realm))
    .map((t) => ({ timer: t, group: group(t), bars: bars(t, now, span) }));
  return ORDER.flatMap((g) => kept.filter((l) => l.group === g));
}

export interface ResetLine {
  at: number;
  /** Fraction of the span. */
  left: number;
  weekly: boolean;
}

/** The resets inside the span, drawn across every lane; a weekly one replaces the daily one. */
export function resets(timers: TimerNow[], span: Span): ResetLine[] {
  const byTime = new Map<number, ResetLine>();
  for (const t of timers) {
    if (t.kind !== "reset" || !t.event) continue;
    const weekly = t.id === "weekly-reset";
    for (const [s] of t.event.occurrences) {
      if (s < span.start || s > span.end) continue;
      if (!weekly && byTime.has(s)) continue;
      byTime.set(s, { at: s, left: at(s, span), weekly });
    }
  }
  return [...byTime.values()].sort((a, b) => a.at - b.at);
}

export interface Tick {
  at: number;
  left: number;
  /** The first hour of a day: labelled with the day rather than the hour. */
  midnight: boolean;
  /** Carries a label; the rest are bare lines, every hour still marked. */
  labelled: boolean;
}

/** A tick every hour; a label every hour on one day, every third on two. Midnight always. */
export function ticks(span: Span, hours: Hours): Tick[] {
  const every = hours === 24 ? 1 : 3;
  const out: Tick[] = [];
  for (let ms = span.start; ms <= span.end; ms += HOUR) {
    const h = new Date(ms).getHours();
    const midnight = h === 0;
    out.push({ at: ms, left: at(ms, span), midnight, labelled: midnight || h % every === 0 });
  }
  return out;
}
