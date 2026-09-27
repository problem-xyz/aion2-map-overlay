/**
 * The plaque's accessible surface: its three glyph buttons have to be named in words, its
 * counter has to read as a sentence rather than as "three slash twelve", and the point the user
 * is walking towards has to be marked once. Every point has a line of its own, labelled or not,
 * and the last steps passed stay above it, as many as Python says. How many rows fit the window
 * is fitRows' to say, tested on its own: jsdom lays nothing out, so here every row is shown.
 *
 * The backend is mocked rather than connected: the plaque talks to the `steps` Qt object, and
 * none of what is asserted here depends on how the payload arrived.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { StepsData } from "@/shared/backend/contract";
import { I18nProvider, catalogs, type PluralCategory } from "@/shared/i18n";

import StepsPage from "./StepsPage";

const mocks = vi.hoisted(() => ({
  data: null as StepsData | null,
  bridge: {
    getData: vi.fn(),
    dragStart: vi.fn(),
    dragEnd: vi.fn(),
    action: vi.fn(),
    setHeight: vi.fn(),
    setHotspot: vi.fn(),
  },
}));

vi.mock("@/shared/backend/BackendProvider", () => ({ useBackendState: () => mocks.data }));
vi.mock("@/shared/backend/hooks", () => ({ useStepsApi: () => mocks.bridge }));

// jsdom has no ResizeObserver, and the plaque measures its rows to see how many fit.
class NoopResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver = NoopResizeObserver;

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function enPlural(key: string, form: PluralCategory): string {
  const message = catalogs.get("en")?.get(key);
  const text = typeof message === "object" ? message[form] : undefined;
  if (text === undefined) throw new Error(`no English ${form} form for ${key}`);
  return text;
}

function fill(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = params[name];
    return value === undefined ? whole : String(value);
  });
}

const DATA: StepsData = {
  title: "To Beluslan",
  done: 2,
  size: "m",
  pinned: false,
  opacity: 0.9,
  language: "en",
  steps: [
    { n: 1, text: "Leave town", color: "#ff0000" },
    { n: 2, text: "Cross the bridge", color: "#00ff00" },
    { n: 3, text: "Follow the road", color: "#0000ff" },
    { n: 4, text: "", color: "#0000ff" },
    { n: 5, text: "", color: "#0000ff" },
  ],
};

function mount(patch: Partial<StepsData> = {}) {
  mocks.data = { ...DATA, ...patch };
  render(
    <I18nProvider initial="en">
      <StepsPage />
    </I18nProvider>,
  );
}

function marked(): HTMLElement[] {
  return [...document.querySelectorAll<HTMLElement>("[aria-current]")];
}

/** The rows on show: the unseen copy that is measured is aria-hidden, and left out. */
function rows(): HTMLElement[] {
  return screen.getAllByRole("listitem");
}

describe("StepsPage", () => {
  beforeEach(() => {
    mocks.bridge.action.mockClear();
  });

  it("names its two glyph buttons in words, and has no size button any more", () => {
    mount();

    expect(screen.getByRole("button", { name: en("steps.pin") })).toBeDefined();
    expect(screen.getByRole("button", { name: en("steps.hide") })).toBeDefined();
    // the size is a scale on the panel's slider now
    expect(screen.getAllByRole("button")).toHaveLength(2);
  });

  it("carries the name as aria-label rather than leaning on the tooltip", () => {
    mount();

    // the accessible-name algorithm falls back to `title`, so a getByRole(name) query alone
    // cannot tell a named button from one that only has a tooltip. This can.
    for (const button of screen.getAllByRole("button")) {
      expect(button.getAttribute("aria-label")).toBeTruthy();
    }
  });

  it("renames the pin button once the plaque is pinned", () => {
    mount({ pinned: true });

    expect(screen.getByRole("button", { name: en("steps.unpin") })).toBeDefined();
    // a pinned plaque keeps the unpin button and nothing else
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("reaches the backend when a button is pressed", async () => {
    const user = userEvent.setup();
    mount();

    await user.click(screen.getByRole("button", { name: en("steps.pin") }));

    expect(mocks.bridge.action).toHaveBeenCalledWith("pin");
  });

  it("reads the counter out as a sentence", () => {
    mount();

    const expected = fill(enPlural("steps.counter", "other"), { done: 2, count: 5 });

    expect(screen.getByRole("img", { name: expected })).toBeDefined();
  });

  it("uses the singular when the route is one point long", () => {
    mount({ done: 0, steps: [{ n: 1, text: "Only stop", color: "#ff0000" }] });

    const expected = fill(enPlural("steps.counter", "one"), { done: 0, count: 1 });

    expect(screen.getByRole("img", { name: expected })).toBeDefined();
  });

  it("marks the nearest step, and only it", () => {
    mount();

    const current = marked();
    expect(current).toHaveLength(1);
    expect(current[0]?.getAttribute("aria-current")).toBe("step");
    expect(current[0]?.textContent).toContain("Follow the road");
  });

  it("lays the selected surface under the nearest step standing still: it is over the game", () => {
    mount();

    const sheens = document.querySelectorAll(".ui-sheen");
    expect(sheens).toHaveLength(1);
    expect(marked()[0]?.contains(sheens[0] ?? null)).toBe(true);
    expect(sheens[0]?.classList.contains("ui-sheen-still")).toBe(true);
  });

  it("gives an unlabelled point a line of its own, and marks it when it is the nearest", () => {
    // everything labelled is done, so the next point is one with no label
    mount({ done: 3 });
    expect(screen.getAllByRole("listitem")).toHaveLength(DATA.steps.length - 3);

    const current = marked();
    expect(current).toHaveLength(1);
    expect(current[0]?.getAttribute("aria-current")).toBe("step");
    expect(current[0]?.textContent).toBe("4");
  });

  it("measures no more than thirty rows, and says how many points are left past them", () => {
    const steps = Array.from({ length: 40 }, (_, i) => ({
      n: i + 1,
      text: `Step ${i + 1}`,
      color: "#ff0000",
    }));
    mount({ steps, done: 0 });

    const items = rows();
    expect(items).toHaveLength(31);
    expect(items[29]?.textContent).toContain("Step 30");
    expect(items[30]?.textContent).toBe(fill(enPlural("steps.more", "other"), { count: 10 }));
  });

  it("lists no step passed when Python sends no count, as before api 14", () => {
    mount();

    expect(rows().filter((item) => item.matches(".passed"))).toHaveLength(0);
  });

  it("lists the last steps passed above the nearest, as many as the map keeps", () => {
    mount({ past: 1 });

    const items = rows();
    expect(items).toHaveLength(4);
    expect(items[0]?.textContent).toBe("2Cross the bridge");
    expect(items[0]?.classList.contains("passed")).toBe(true);
    expect(items[0]?.hasAttribute("aria-current")).toBe(false);
    expect(items[1]?.getAttribute("aria-current")).toBe("step");
  });

  it("lists no more steps passed than there are", () => {
    mount({ past: 5 });

    expect(rows().filter((item) => item.matches(".passed"))).toHaveLength(DATA.done);
  });

  it("adds no such line when every row fits", () => {
    mount();

    expect(rows().filter((item) => item.matches(".so-more"))).toHaveLength(0);
  });

  it("draws the resize strips while loose, and none once pinned", () => {
    mount({ grip: 10 });
    expect(document.querySelectorAll(".so-grip")).toHaveLength(3);
    const card = document.querySelector<HTMLElement>(".so-card");
    expect(card?.style.getPropertyValue("--so-grip")).toBe("10px");

    mount({ pinned: true });
    expect(document.querySelectorAll(".so-card.pinned .so-grip")).toHaveLength(0);
  });

  it("keeps the whole route name reachable, however the title is cut", () => {
    mount({ title: "A very long route name that the plaque cuts off with an ellipsis" });

    expect(
      screen.getByText("A very long route name that the plaque cuts off with an ellipsis"),
    ).toHaveProperty("title", "A very long route name that the plaque cuts off with an ellipsis");
  });

  it("shows a step's quest star after its number, and none where it has none", () => {
    mount({
      done: 0,
      steps: [
        { n: 1, text: "Talk to the elder", color: "#f2b544", icon: "main" },
        { n: 2, text: "Pick the herbs", color: "#22c55e" },
      ],
    });

    const items = rows();
    expect(items[0]?.querySelector("svg.so-icon")).not.toBeNull();
    expect(items[1]?.querySelector("svg.so-icon")).toBeNull();
  });

  it("draws a step's quest star first, else the icon of what it sits on", () => {
    mount({
      done: 0,
      steps: [
        { n: 1, text: "Talk to the elder", color: "#f2b544", icon: "main", object: "teleport" },
        { n: 2, text: "Take the teleport", color: "#b48cff", object: "teleport" },
        { n: 3, text: "Walk on", color: "#6ea8ff" },
      ],
    });

    expect(rows().map((row) => row.querySelectorAll(".so-icon").length)).toEqual([1, 1, 0]);
  });

  it("sizes itself from the scale Python sends", () => {
    mount({ scale: 1.4 });
    const card = document.querySelector<HTMLElement>(".so-card");
    expect(card?.style.getPropertyValue("--so-scale")).toBe("1.4");
  });

  it("offers the step arrows only while progress counts", () => {
    mount({ switch: false });
    expect(screen.queryByRole("button", { name: en("steps.stepNext") })).toBeNull();
  });

  it("takes a step back and a step forward, pinned or not", async () => {
    const user = userEvent.setup();
    mount({ switch: true, pinned: true });

    await user.click(screen.getByRole("button", { name: en("steps.stepBack") }));
    await user.click(screen.getByRole("button", { name: en("steps.stepNext") }));

    expect(mocks.bridge.action.mock.calls).toEqual([["prev"], ["next"]]);
  });

  it("has no step to take back before the first point is done", () => {
    mount({ switch: true, done: 0 });

    expect(screen.getByRole("button", { name: en("steps.stepBack") })).toHaveProperty(
      "disabled",
      true,
    );
    expect(screen.getByRole("button", { name: en("steps.stepNext") })).toHaveProperty(
      "disabled",
      false,
    );
  });
});
