/**
 * The timers' marks: every kind the schedule ships has a drawing and a hue, a name this build does
 * not know still draws something neutral, and the mark stays out of the accessibility tree --
 * the event's name beside it says the same.
 */

import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import schedule from "../../../../assets/timers/schedule.json";

import TimerMark from "./TimerMark";
import { REALM_HUES, isTimerIcon, timerHue, timerLayers } from "./timerMarks";

const PATH = /^[MmLlHhVvCcSsQqTtAaZz0-9.,\s-]+$/;

describe("timerMarks", () => {
  it("draws every icon the bundled schedule names", () => {
    for (const event of schedule.events) {
      expect(isTimerIcon(event.icon), event.id).toBe(true);
    }
  });

  it("draws each icon as paths with something to paint", () => {
    for (const name of ["demon", "vortex", "fox", "siege", "daily", "weekly"]) {
      const layers = timerLayers(name);
      expect(layers.length, name).toBeGreaterThan(0);
      for (const layer of layers) {
        expect(layer.d, name).toMatch(PATH);
        expect(layer.fill ?? layer.stroke, name).toBeTruthy();
      }
    }
  });

  it("gives every boss the same red, apart from every other kind", () => {
    expect(timerHue("demon")).toBe("#f07178");
    const others = ["vortex", "fox", "siege", "daily"].map(timerHue);
    expect(others).not.toContain(timerHue("demon"));
    expect(new Set(others).size).toBe(others.length);
  });

  it("keeps the realms' hues apart from each other", () => {
    expect(REALM_HUES.abyss).not.toBe(REALM_HUES.world);
  });

  it("draws an unknown icon as a neutral token rather than as some other kind", () => {
    const unknown = timerLayers("dragon");
    for (const known of ["demon", "vortex", "fox", "siege", "daily", "weekly"]) {
      expect(unknown).not.toBe(timerLayers(known));
    }
    expect(timerHue("dragon")).toBe(timerHue("daily"));
  });
});

describe("TimerMark", () => {
  it("is decoration: hidden, unfocusable, painted in its kind's hue", () => {
    const { container } = render(<TimerMark icon="vortex" size="lg" />);
    const mark = container.firstElementChild as HTMLElement;
    expect(mark.getAttribute("aria-hidden")).toBe("true");
    expect(mark.className).toContain("ui-tmark-lg");
    expect(mark.style.getPropertyValue("--tmark-hue")).toBe("#a78bfa");
    expect(container.querySelector("svg")?.getAttribute("focusable")).toBe("false");
    expect(container.querySelectorAll("path").length).toBe(timerLayers("vortex").length);
  });
});
