/**
 * The mock's timers follow the app's rules closely enough for a page: the same running rift at
 * the same moment the Python tests use, the Korean server groups, the world bosses' cycles.
 */

import { describe, expect, it } from "vitest";

import bossDoc from "../../../assets/timers/world-bosses.json";

import { makeState } from "./mockState";
import { makeTimers } from "./mockTimers";

const NOW = Date.UTC(2026, 9, 5, 12, 5); // a Monday; the noon rift is five minutes in

describe("makeTimers", () => {
  it("has the noon rift running with entry open, as timers/view.py does", () => {
    const timers = makeTimers(makeState().settings, NOW);
    const rift = timers.events.find((e) => e.id === "rift");
    expect(rift?.live).toEqual({ start: Date.UTC(2026, 9, 5, 12), end: Date.UTC(2026, 9, 5, 13) });
    expect(rift?.entryCloses).toBe(Date.UTC(2026, 9, 5, 12, 10));
    expect(rift?.next?.start).toBe(Date.UTC(2026, 9, 5, 15));
  });

  it("puts the user's choices over the defaults", () => {
    const settings = makeState().settings;
    settings.timers_events = { rift: { lead: 10 } };
    const timers = makeTimers(settings, NOW);
    expect(timers.events.find((e) => e.id === "rift")?.lead).toBe(10);
    expect(timers.events.find((e) => e.id === "daily-reset")?.lead).toBe(0);
  });

  it("names Korea's server groups", () => {
    const settings = { ...makeState().settings, timers_region: "kr" };
    expect(makeTimers(settings, NOW).serverGroups).toEqual(["1", "2", "3"]);
  });

  it("lists the world bosses a cycle and a kill apart", () => {
    // six hours past the reading, whenever it was made: every spawn by then is worked out
    const timers = makeTimers(makeState().settings, Date.parse(bossDoc.readAt) + 6 * 3_600_000);
    const danar = timers.bosses.find((b) => b.id === "melted-danar");
    expect(danar?.estimated).toBe(true);
    const gaps = danar!.spawns.slice(1).map((s, i) => s - danar!.spawns[i]!);
    expect(new Set(gaps)).toEqual(new Set([1800_000 + 90_000]));
  });
});
