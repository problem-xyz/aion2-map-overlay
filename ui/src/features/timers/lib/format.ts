/**
 * How the timers write time: countdowns, clock times, days and how often an event comes round.
 * Every function takes the translate function, so the words are the catalogue's.
 */

import type { TimerEvent } from "@/shared/backend/contract";
import type { TFunction } from "@/shared/i18n";

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

const two = (n: number) => String(n).padStart(2, "0");

/** 44:32 under an hour, 4h 44m under a day, 2d 4h beyond: as precise as the distance is worth. */
export function countdown(ms: number, t: TFunction): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 3600) return `${Math.floor(s / 60)}:${two(s % 60)}`;
  const h = Math.floor(s / 3600);
  if (h < 24) return t("timers.time.hm", { h, m: two(Math.floor((s % 3600) / 60)) });
  return t("timers.time.dh", { d: Math.floor(h / 24), h: h % 24 });
}

/** A length of time rather than one counting down: "30 min", "1h 30m", "12h 00m". */
export function duration(ms: number, t: TFunction): string {
  const minutes = Math.round(ms / MIN);
  if (minutes < 60) return t("timers.lasts", { count: minutes });
  return countdown(minutes * MIN, t);
}

const clocks = new Map<string, Intl.DateTimeFormat>();

/** 15:00, or 3:00 PM with the 12-hour clock: in the player's own time zone. */
export function clock(ms: number, locale: string, twelve: boolean): string {
  const key = `${locale}|${twelve}`;
  let f = clocks.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(locale, {
      hour: twelve ? "numeric" : "2-digit",
      minute: "2-digit",
      hourCycle: twelve ? "h12" : "h23",
    });
    clocks.set(key, f);
  }
  return f.format(ms);
}

const weekdays = new Map<string, Intl.DateTimeFormat>();

function weekday(ms: number, locale: string): string {
  let f = weekdays.get(locale);
  if (!f) {
    f = new Intl.DateTimeFormat(locale, { weekday: "short" });
    weekdays.set(locale, f);
  }
  return f.format(ms);
}

function startOfDay(ms: number): number {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** "today", "tomorrow", or the weekday: which day a moment falls on, from now. */
export function day(ms: number, now: number, locale: string, t: TFunction): string {
  const days = Math.round((startOfDay(ms) - startOfDay(now)) / DAY);
  if (days === 0) return t("timers.day.today");
  if (days === 1) return t("timers.day.tomorrow");
  return weekday(ms, locale);
}

/**
 * How often the event comes round, read off its occurrences: "every hour", "every 3 h", "daily",
 * or its weekdays. A one-off, or one whose spacing is not regular, says nothing.
 */
export function frequency(e: TimerEvent, locale: string, t: TFunction): string {
  const starts = e.occurrences.map(([s]) => s);
  const week = e.weekStarts ?? [];
  if (starts.length < 2 && week.length === 0) return "";
  const gaps = new Set(starts.slice(1).map((s, i) => s - (starts[i] ?? s)));
  if (week.length === 0 && gaps.size === 1) {
    const gap = [...gaps][0] ?? 0;
    if (gap === HOUR) return t("timers.every.hour");
    if (gap < DAY && gap % HOUR === 0) return t("timers.every.hours", { count: gap / HOUR });
    if (gap === DAY) return t("timers.every.day");
  }
  // weekly: the weekdays it falls on, in the player's own time, Monday first
  const order = (ms: number) => (new Date(ms).getDay() + 6) % 7;
  const seen = new Map<number, string>();
  for (const s of e.weekStarts?.length ? e.weekStarts : starts)
    seen.set(order(s), weekday(s, locale));
  return [...seen.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(([, name]) => name)
    .join(", ");
}

/** "30 min" of an event's length, or "entry 10 min" for one whose entry closes first. */
export function span(e: TimerEvent, t: TFunction): string {
  if (e.entryMin > 0) return t("timers.entry", { count: e.entryMin });
  if (e.durationMin > 0) return t("timers.lasts", { count: e.durationMin });
  return "";
}

/** The schedule's date, "2026-10-02", as the reader writes dates: "2 Oct" in English. */
export function scheduleDate(iso: string, locale: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const at = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" }).format(at);
}
