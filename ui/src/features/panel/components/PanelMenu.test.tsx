/**
 * The section tiles: a tablist the arrows walk, one key per section, and E for the editor,
 * whose button sits over the routes now rather than beside the tiles.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { I18nProvider } from "@/shared/i18n";

import PanelMenu, { type PanelSection } from "./PanelMenu";

function mount(active: PanelSection = "routes", updateWaiting = false) {
  const onSelect = vi.fn();
  const onEditor = vi.fn();
  render(
    <I18nProvider initial="en">
      <PanelMenu
        active={active}
        onSelect={onSelect}
        onEditor={onEditor}
        updateWaiting={updateWaiting}
      />
      <input aria-label="field" />
    </I18nProvider>,
  );
  return { onSelect, onEditor };
}

describe("PanelMenu", () => {
  it("is a named tablist of three sections, the active one selected", () => {
    mount("progress");

    expect(screen.getByRole("tablist", { name: "Sections" })).toBeDefined();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "RRoutes",
      "PProgress",
      "SSettings",
    ]);
    expect(screen.getByRole("tab", { selected: true }).textContent).toContain("Progress");
    expect(screen.queryByRole("button", { name: /Editor/ })).toBeNull();
  });

  it("switches sections by key, whatever the keyboard layout, and opens the editor on E", async () => {
    const user = userEvent.setup();
    const { onSelect, onEditor } = mount();

    await user.keyboard("[KeyS]");
    expect(onSelect).toHaveBeenLastCalledWith("settings");
    await user.keyboard("[KeyP]");
    expect(onSelect).toHaveBeenLastCalledWith("progress");
    await user.keyboard("[KeyE]");
    expect(onEditor).toHaveBeenCalledTimes(1);
  });

  it("leaves keys typed in a field to the field", async () => {
    const user = userEvent.setup();
    const { onSelect, onEditor } = mount();

    await user.click(screen.getByRole("textbox", { name: "field" }));
    await user.keyboard("spe");

    expect(onSelect).not.toHaveBeenCalled();
    expect(onEditor).not.toHaveBeenCalled();
  });

  it("walks the tabs with the arrows", async () => {
    const user = userEvent.setup();
    const { onSelect } = mount("routes");

    screen.getByRole("tab", { selected: true }).focus();
    await user.keyboard("{ArrowLeft}");

    expect(onSelect).toHaveBeenLastCalledWith("settings");
  });

  it("marks Settings while an update waits there", () => {
    mount("routes", true);

    expect(screen.getByRole("tab", { name: /Settings/ }).textContent).toContain(
      "An update is available",
    );
  });

  it("lays the living sheen under the selected tile alone, hidden from a screen reader", () => {
    mount("settings");

    const sheens = document.querySelectorAll(".ui-sheen");
    expect(sheens).toHaveLength(1);
    expect(screen.getByRole("tab", { selected: true }).contains(sheens[0] ?? null)).toBe(true);
    expect(sheens[0]?.getAttribute("aria-hidden")).toBe("true");
  });
});
