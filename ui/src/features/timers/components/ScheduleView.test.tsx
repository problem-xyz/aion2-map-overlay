/**
 * The schedule: soonest first, what runs leading, the filters narrowing it, only what is switched
 * on, and the world bosses kept to a few outside their own tab, where every one of them is listed.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TimerEvent, WorldBossTimer } from "@/shared/backend/contract";
import { I18nProvider } from "@/shared/i18n";

import { bossNow, eventNow, type Filter, type Realm } from "../lib/model";

import ScheduleView from "./ScheduleView";

const MIN = 60_000;
const NOW = Date.UTC(2026, 9, 5, 12, 5);

function event(id: string, kind: TimerEvent["kind"], start: number, minutes = 30): TimerEvent {
  return {
    id,
    name: id,
    kind,
    realm: kind === "boss" ? "abyss" : null,
    icon: kind === "boss" ? "demon" : "vortex",
    durationMin: minutes,
    entryMin: 0,
    shown: true,
    lead: 5,
    signal: "chime",
    live: null,
    entryCloses: null,
    next: null,
    occurrences: [[start, start + minutes * MIN]],
  };
}

function boss(i: number): WorldBossTimer {
  const spawn = NOW + (10 + i) * MIN;
  return {
    id: `boss-${i}`,
    name: `World Boss ${i}`,
    area: "",
    level: 45,
    respawnS: 1800,
    drops: [],
    // the last one is switched off
    shown: i < 4,
    spawn,
    up: false,
    estimated: false,
    spawns: [spawn],
  };
}

function mount(filter: Filter = "all", realm: Realm = "all") {
  const off = { ...event("Off", "event", NOW + 5 * MIN), shown: false };
  const timers = [
    eventNow(off, NOW),
    eventNow(event("Siege", "event", NOW + 60 * MIN), NOW),
    eventNow(event("Running", "event", NOW - 2 * MIN), NOW),
    eventNow(event("Abyss Boss", "boss", NOW + 90 * MIN), NOW),
    ...[0, 1, 2, 3, 4].map((i) => bossNow(boss(i), NOW, 5)),
  ];
  const onFilter = vi.fn();
  const onRealm = vi.fn();
  const onSettings = vi.fn();
  render(
    <I18nProvider initial="en">
      <ScheduleView
        timers={timers}
        now={NOW}
        twelve={false}
        filter={filter}
        realm={realm}
        onFilter={onFilter}
        onRealm={onRealm}
        bossesReadAt={NOW - 60 * MIN}
        wrongCycle={[]}
        onSettings={onSettings}
      />
    </I18nProvider>,
  );
  return { onFilter, onRealm, onSettings };
}

const names = () =>
  within(document.querySelector(".tm-list") as HTMLElement)
    .getAllByRole("listitem")
    .map((li) => li.querySelector(".tm-row-name")?.textContent);

describe("ScheduleView", () => {
  it("leads with what runs, then the soonest, three world bosses at most", () => {
    mount();
    expect(names()).toEqual([
      "Running",
      "World Boss 0",
      "World Boss 1",
      "World Boss 2",
      "Siege",
      "Abyss Boss",
    ]);
    expect(screen.getByRole("button", { name: "1 more world boss" })).toBeDefined();
  });

  it("takes the world bosses' own tab for the rest of them", async () => {
    const { onFilter, onRealm } = mount();
    await userEvent.click(screen.getByRole("button", { name: "1 more world boss" }));
    expect(onFilter).toHaveBeenCalledWith("boss");
    expect(onRealm).toHaveBeenCalledWith("world");
  });

  it("lists every world boss in their tab, the one switched off said to be", () => {
    mount("boss", "world");
    expect(names()).toHaveLength(5);
    expect(screen.getAllByText("switched off")).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /more world/ })).toBeNull();
  });

  it("leaves what is switched off out of every other list", () => {
    mount("event");
    expect(names()).not.toContain("Off");
  });

  it("keeps the events alone under Events", () => {
    mount("event");
    expect(names()).toEqual(["Running", "Siege"]);
  });
  it("says where to switch timers on when a list has none", async () => {
    const onSettings = vi.fn();
    render(
      <I18nProvider initial="en">
        <ScheduleView
          timers={[eventNow({ ...event("Off", "event", NOW + MIN), shown: false }, NOW)]}
          now={NOW}
          twelve={false}
          filter="all"
          realm="all"
          onFilter={vi.fn()}
          onRealm={vi.fn()}
          bossesReadAt={null}
          wrongCycle={[]}
          onSettings={onSettings}
        />
      </I18nProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Open Settings" }));
    expect(onSettings).toHaveBeenCalled();
  });

  it("offers no filter when there is no boss to tell the events apart from", () => {
    render(
      <I18nProvider initial="en">
        <ScheduleView
          timers={[eventNow(event("Rift", "event", NOW + MIN), NOW)]}
          now={NOW}
          twelve={false}
          filter="boss"
          realm="world"
          onFilter={vi.fn()}
          onRealm={vi.fn()}
          bossesReadAt={null}
          wrongCycle={[]}
        />
      </I18nProvider>,
    );
    expect(screen.queryByRole("radiogroup")).toBeNull();
    expect(names()).toEqual(["Rift"]);
  });
});
