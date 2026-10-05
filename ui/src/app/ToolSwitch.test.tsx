/**
 * The switch between the panel's tools: a named tablist the arrows move along, the gear one of its
 * tabs, and the mark of a waiting update on the gear, where the updates now live.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import ToolSwitch, { type Tool } from "./ToolSwitch";

function mount(active: Tool = "map", updateWaiting = false) {
  const onSelect = vi.fn();
  render(
    <I18nProvider initial="en">
      <ToolSwitch active={active} onSelect={onSelect} updateWaiting={updateWaiting} />
    </I18nProvider>,
  );
  return onSelect;
}

describe("ToolSwitch", () => {
  it("is a named tablist of the map, the timers and the app's settings", () => {
    mount("timers");
    expect(screen.getByRole("tablist", { name: "Tools" })).toBeDefined();
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.getAttribute("aria-selected"))).toEqual(["false", "true", "false"]);
    expect(screen.getByRole("tab", { name: "App settings" })).toBeDefined();
  });

  it("moves along the tabs with the arrows, round from either end to the other", async () => {
    const onSelect = mount("app");
    screen.getByRole("tab", { name: "App settings" }).focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(onSelect).toHaveBeenLastCalledWith("map");
    expect(document.activeElement).toBe(screen.getByRole("tab", { name: "Map" }));
    await userEvent.keyboard("{ArrowLeft}");
    expect(onSelect).toHaveBeenLastCalledWith("app");
  });

  it("marks the gear while an update waits behind it", () => {
    mount("map", true);
    expect(screen.getByRole("tab", { name: "App settings" }).textContent).toContain(
      "An update is available",
    );
  });
});
