/**
 * The timeline's layout: where the span starts, bars placed and clipped by time, the world bosses'
 * spawns as estimated past the reading, the resets merged, and the hours labelled.
 */

import { describe, expect, it } from "vitest";

import type { TimerEvent, WorldBossTimer } from "@/shared/backend/contract";

import { bossNow, eventNow } from "./model";
import { lanes, resets, ticks, timelineSpan } from "./timeline";

const MIN = 60_000;
const HOUR = 60 * MIN;
// local time: the span and the hour labels follow the player's own clock
const NOW = new Date(2026, 9, 5, 12, 20).getTime();
const TOP = new Date(2026, 9, 5, 11, 0).getTime();

function must<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("expected a value");
  return value;
}

function event(
  id: string,
  kind: TimerEvent["kind"],
  spans: [number, number][],
  realm: TimerEvent["realm"] = null,
): TimerEvent {
  return {
    id,
    name: id,
    kind,
    realm,
    icon: kind === "boss" ? "demon" : kind === "reset" ? "daily" : "vortex",
    durationMin: 60,
    entryMin: 0,
    shown: true,
    lead: 5,
    signal: "chime",
    live: null,
    entryCloses: null,
    next: null,
    occurrences: spans,
  };
}

function boss(spawns: number[], estimated = false): WorldBossTimer {
  return {
    id: "w",
    name: "World",
    area: "",
    level: 45,
    respawnS: 3600,
    drops: [],
    shown: true,
    spawn: must(spawns[0]),
    up: false,
    estimated,
    spawns,
  };
}

describe("timelineSpan", () => {
  it("starts at the top of the hour before now and runs one or two days", () => {
    expect(timelineSpan(NOW, 24)).toEqual({ start: TOP, end: TOP + 24 * HOUR });
    expect(timelineSpan(NOW, 48).end).toBe(TOP + 48 * HOUR);
  });
});

describe("lanes", () => {
  const span = timelineSpan(NOW, 24);

  it("places bars by time, clips them to the span and says which are past or running", () => {
    const rift = event("rift", "event", [
      [TOP - HOUR, TOP + 30 * MIN],
      [NOW - 10 * MIN, NOW + 50 * MIN],
      [TOP + 12 * HOUR, TOP + 13 * HOUR],
      [TOP + 30 * HOUR, TOP + 31 * HOUR],
    ]);
    const lane = must(lanes([eventNow(rift, NOW)], NOW, span, "all", "all")[0]);
    expect(lane.bars).toHaveLength(3);
    const [first, live, ahead] = [0, 1, 2].map((i) => must(lane.bars[i]));
    if (!first || !live || !ahead) throw new Error("three bars");
    expect(first).toMatchObject({ left: 0, state: "past" });
    expect(first.width).toBeCloseTo(0.5 / 24);
    expect(live.state).toBe("live");
    expect(ahead.left).toBeCloseTo(0.5);
    expect(ahead.width).toBeCloseTo(1 / 24);
  });

  it("lists events, then the Abyss's bosses, then the world's, under the filters", () => {
    const timers = [
      bossNow(boss([NOW + HOUR]), NOW, 5),
      eventNow(event("abyss", "boss", [[NOW + HOUR, NOW + HOUR]], "abyss"), NOW),
      eventNow(event("rift", "event", [[NOW + HOUR, NOW + 2 * HOUR]]), NOW),
      eventNow(event("daily-reset", "reset", [[NOW + HOUR, NOW + HOUR]]), NOW),
    ];
    const ids = (f: "all" | "event" | "boss", r: "all" | "world" | "abyss" = "all") =>
      lanes(timers, NOW, span, f, r).map((l) => l.timer.id);
    expect(ids("all")).toEqual(["rift", "abyss", "w"]);
    expect(ids("event")).toEqual(["rift"]);
    expect(ids("boss", "world")).toEqual(["w"]);
  });

  it("marks a world boss's spawns after the one read in the game as estimated", () => {
    const read = NOW + HOUR;
    const lane = must(
      lanes([bossNow(boss([read, read + HOUR]), NOW, 5)], NOW, span, "all", "all")[0],
    );
    expect(lane.bars.map((b) => b.estimated)).toEqual([false, true]);
  });
});

describe("resets", () => {
  it("keeps the weekly one where both fall at once", () => {
    const at = TOP + 22 * HOUR;
    const daily = eventNow(event("daily-reset", "reset", [[at, at]]), NOW);
    const weekly = eventNow(event("weekly-reset", "reset", [[at, at]]), NOW);
    const lines = resets([daily, weekly], timelineSpan(NOW, 24));
    expect(lines).toEqual([{ at, left: 22 / 24, weekly: true }]);
  });
});

describe("ticks", () => {
  it("marks every hour, labels every hour on one day and every third on two, midnight always", () => {
    const one = ticks(timelineSpan(NOW, 24), 24);
    expect(one).toHaveLength(25);
    expect(one.every((t) => t.labelled)).toBe(true);
    const midnight = one.find((t) => t.midnight);
    expect(midnight?.at).toBe(new Date(2026, 9, 6, 0, 0).getTime());

    const two = ticks(timelineSpan(NOW, 48), 48);
    expect(two).toHaveLength(49);
    const labelled = two.filter((t) => t.labelled).map((t) => new Date(t.at).getHours());
    expect(labelled.every((h) => h % 3 === 0)).toBe(true);
  });
});
