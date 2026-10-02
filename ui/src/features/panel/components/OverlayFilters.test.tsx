/**
 * The row of filters under Start: each slot switches its own setting and nothing else.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider, catalogs } from "@/shared/i18n";

import OverlayFilters, { type OverlayFiltersProps } from "./OverlayFilters";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function mount(props: Partial<OverlayFiltersProps> = {}) {
  const all: OverlayFiltersProps = {
    cubes: false,
    resources: false,
    picked: [],
    available: ["odyle", "orichalcum", "ruby"],
    traces: true,
    seals: true,
    onCubes: vi.fn(),
    onResources: vi.fn(),
    onPick: vi.fn(),
    onTraces: vi.fn(),
    onSeals: vi.fn(),
    ...props,
  };
  render(
    <I18nProvider initial="en">
      <OverlayFilters {...all} />
    </I18nProvider>,
  );
  return all;
}

function box(key: string): HTMLInputElement {
  return screen.getByRole<HTMLInputElement>("checkbox", { name: en(key) });
}

describe("OverlayFilters", () => {
  it("shows each filter as it stands", () => {
    mount({ cubes: true, traces: false, seals: true });

    expect(box("panel.filters.cubes").checked).toBe(true);
    expect(box("panel.filters.traces").checked).toBe(false);
    expect(box("panel.filters.seals").checked).toBe(true);
  });

  it("switches the one filter clicked", () => {
    const props = mount();

    fireEvent.click(box("panel.filters.seals"));

    expect(props.onSeals).toHaveBeenCalledWith(false);
    expect(props.onCubes).not.toHaveBeenCalled();
    expect(props.onTraces).not.toHaveBeenCalled();
    expect(props.onResources).not.toHaveBeenCalled();
  });
});

function openList() {
  fireEvent.click(screen.getByRole("button", { name: en("panel.filters.resourcesPick") }));
}

describe("the resources filter", () => {
  it("lists the map's resources by name, the picked ones ticked", () => {
    mount({ picked: ["ruby"] });
    openList();

    expect(box("common.resources.odyle").checked).toBe(false);
    expect(box("common.resources.ruby").checked).toBe(true);
    expect(screen.queryByRole("checkbox", { name: en("common.resources.aria") })).toBeNull();
  });

  it("ticking a resource adds it in the list's order and turns the switch on", () => {
    const props = mount({ picked: ["ruby"] });
    openList();

    fireEvent.click(box("common.resources.odyle"));

    expect(props.onPick).toHaveBeenCalledWith(["odyle", "ruby"]);
    expect(props.onResources).toHaveBeenCalledWith(true);
  });

  it("unticking one leaves the switch as it is", () => {
    const props = mount({ resources: true, picked: ["odyle", "ruby"] });
    openList();

    fireEvent.click(box("common.resources.odyle"));

    expect(props.onPick).toHaveBeenCalledWith(["ruby"]);
    expect(props.onResources).not.toHaveBeenCalled();
  });

  it("turning the switch on with nothing picked opens the list", () => {
    const props = mount();

    fireEvent.click(box("panel.filters.resources"));

    expect(props.onResources).toHaveBeenCalledWith(true);
    expect(box("common.resources.odyle")).toBeTruthy();
  });

  it("Escape closes the list", () => {
    mount();
    openList();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("checkbox", { name: en("common.resources.odyle") })).toBeNull();
  });

  it("offers no more once five are ticked, and says why", () => {
    mount({
      available: ["odyle", "orichalcum", "sapphire", "diamond", "ruby", "aria"],
      picked: ["odyle", "orichalcum", "sapphire", "diamond", "ruby"],
    });
    openList();

    expect(box("common.resources.aria").disabled).toBe(true);
    expect(box("common.resources.ruby").disabled).toBe(false); // a ticked one can be unticked
    expect(screen.getByText(/Up to 5 at a time/)).toBeTruthy();
  });

  it("says so when the map has none", () => {
    mount({ available: [] });
    openList();

    expect(screen.getByText(en("panel.filters.resourcesNone"))).toBeTruthy();
  });
});
