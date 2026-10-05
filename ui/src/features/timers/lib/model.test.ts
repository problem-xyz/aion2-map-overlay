/**
 * The timers at a moment, on the page: what is running, what is next, how a world boss's next
 * spawn is told apart from the one the game's list gave, and the words for times.
 */

import { describe, expect, it } from "vitest";

import type { TimerEvent, WorldBossTimer } from "@/shared/backend/contract";
import { catalogs, createT } from "@/shared/i18n";

import { countdown, duration, frequency, span } from "./format";
import { bossNow, byTime, eventNow, far, passes, soon } from "./model";

const MIN = 60_000;
const HOUR = 60 * MIN;
const T0 = Date.UTC(2026, 9, 5, 12, 0);
const english = catalogs.get("en")!;
const t = createT({
  locale: "en",
  catalog: english,
  fallback: english,
  formatNumber: (v) => String(v),
});

function rift(occurrences: [number, number][]): TimerEvent {
  return {
    id: "rift",
    name: "Spacetime Rift",
    kind: "event",
    realm: null,
    icon: "vortex",
    durationMin: 60,
    entryMin: 10,
    shown: true,
    lead: 5,
    signal: "chime",
    live: null,
    entryCloses: null,
    next: null,
    occurrences,
  };
}

const RIFTS: [number, number][] = [0, 3, 6].map((h) => [T0 + h * HOUR, T0 + (h + 1) * HOUR]);

describe("eventNow", () => {
  it("is live with entry open for the first ten minutes, then waits for the next one", () => {
    const open = eventNow(rift(RIFTS), T0 + 5 * MIN);
    expect(open.live?.entryCloses).toBe(T0 + 10 * MIN);
    expect(open.target).toBe(T0 + 10 * MIN);
    const closed = eventNow(rift(RIFTS), T0 + 20 * MIN);
    expect(closed.live).toBeNull();
    expect(closed.next).toBe(T0 + 3 * HOUR);
  });

  it("is due soon inside its reminder window and quiet more than an hour off", () => {
    expect(soon(eventNow(rift(RIFTS), T0 + 2 * HOUR + 56 * MIN), T0 + 2 * HOUR + 56 * MIN)).toBe(
      true,
    );
    expect(far(eventNow(rift(RIFTS), T0 + 20 * MIN), T0 + 20 * MIN)).toBe(true);
  });
});

describe("bossNow", () => {
  const boss = (spawn: number, estimated: boolean, spawns: number[]): WorldBossTimer => ({
    id: "aed",
    name: "Black Warrior Aed",
    area: "",
    level: 45,
    respawnS: 1800,
    shown: true,
    spawn,
    up: false,
    estimated,
    spawns,
  });

  it("tells the game's spawn from the ones worked out after it", () => {
    const cycle = 31.5 * MIN;
    const spawns = [T0, T0 + cycle, T0 + 2 * cycle];
    expect(bossNow(boss(T0, false, spawns), T0 - MIN, 5).estimated).toBe(false);
    expect(bossNow(boss(T0, false, spawns), T0 + 10 * MIN, 5).estimated).toBe(true);
  });

  it("is up for three minutes after a spawn", () => {
    const b = bossNow(boss(T0, false, [T0]), T0 + MIN, 5);
    expect(b.live).not.toBeNull();
    expect(bossNow(boss(T0, false, [T0]), T0 + 4 * MIN, 5).live).toBeNull();
  });
});

describe("order and filters", () => {
  it("puts what runs first, then the soonest", () => {
    const later = eventNow(rift([[T0 + 2 * HOUR, T0 + 3 * HOUR]]), T0);
    const running = eventNow(rift(RIFTS), T0 + MIN);
    expect([later, running].sort(byTime)[0]).toBe(running);
  });

  it("keeps bosses of the realm asked for", () => {
    const abyss = { ...eventNow(rift(RIFTS), T0), kind: "boss" as const, realm: "abyss" as const };
    expect(passes(abyss, "boss", "abyss")).toBe(true);
    expect(passes(abyss, "boss", "world")).toBe(false);
    expect(passes(abyss, "event", "all")).toBe(false);
  });
});

describe("format", () => {
  it("counts down as precisely as the distance is worth", () => {
    expect(countdown(44 * MIN + 32_000, t)).toBe("44m 32s");
    expect(countdown(5 * MIN + 2_000, t)).toBe("5m 02s");
    expect(countdown(4 * HOUR + 44 * MIN, t)).toBe("4h 44m");
    expect(countdown(52 * HOUR, t)).toBe("2d 4h");
    expect(countdown(-5_000, t)).toBe("0s");
  });

  it("writes a cycle as a length", () => {
    expect(duration(30 * MIN, t)).toBe("30 min");
    expect(duration(90 * MIN, t)).toBe("1h 30m");
  });

  it("reads how often an event comes round off its occurrences", () => {
    expect(frequency(rift(RIFTS), "en", t)).toBe("every 3 h");
    const hourly: [number, number][] = [0, 1, 2].map((h) => [
      T0 + h * HOUR,
      T0 + h * HOUR + 10 * MIN,
    ]);
    expect(frequency(rift(hourly), "en", t)).toBe("every hour");
    expect(span(rift(RIFTS), t)).toBe("entry 10 min");
  });
});
