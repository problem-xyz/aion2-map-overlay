/**
 * The toolbar: the map menu, the name edited in place, Save only when there is something to
 * save, and the Share menu with the four ways a route leaves the editor.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { MapInfo } from "@/shared/backend/contract";

import { EditorWrap, stubActions, stubState } from "../testing";

import Toolbar from "./Toolbar";

const map = (id: string, label: string): MapInfo => ({
  id,
  label,
  size: [4096, 4096],
  thumb: "",
  tiles: { ready: true, zMax: 4, tile: 256 },
  objects: [],
});
const MAPS = [map("altgard", "Altgard"), map("verteron", "Verteron")];

function mount(dirty = false) {
  const actions = stubActions();
  render(
    <EditorWrap
      state={stubState({ name: "Altgard loop", dirty, maps: MAPS, mapId: "altgard" })}
      actions={actions}
    >
      <Toolbar />
    </EditorWrap>,
  );
  return actions;
}

describe("Toolbar map menu", () => {
  const chip = () => screen.getByRole("button", { name: "Map Altgard" });

  it("comes first in the bar, before the route's name", () => {
    mount();

    const name = screen.getByRole("textbox", { name: "Route name" });
    // DOCUMENT_POSITION_FOLLOWING: the name comes after the map chip
    expect(chip().compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("opens on the checked map and switches to the one picked", async () => {
    const user = userEvent.setup();
    const actions = mount();

    await user.click(chip());
    const items = screen.getAllByRole("menuitemradio");
    expect(items.map((i) => [i.textContent, i.getAttribute("aria-checked")])).toEqual([
      ["Altgard", "true"],
      ["Verteron", "false"],
    ]);
    expect(document.activeElement).toBe(items[0]);

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(items[1]);
    await user.keyboard("{Enter}");
    expect(actions.changeMap).toHaveBeenCalledWith("verteron");
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("opens from the keyboard and closes when the focus leaves it", async () => {
    const user = userEvent.setup();
    mount();

    chip().focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("menu")).toBeDefined();
    await user.tab();
    expect(screen.queryByRole("menu")).toBeNull();
  });
});

describe("Toolbar", () => {
  it("edits the route's name in place", async () => {
    const user = userEvent.setup();
    const actions = mount();

    await user.type(screen.getByRole("textbox", { name: "Route name" }), "!");
    expect(actions.setName).toHaveBeenLastCalledWith("Altgard loop!");
  });

  it("offers Save only with unsaved changes, and reads Saved without them", () => {
    mount(true);
    expect(screen.getByRole("button", { name: "Save" }).hasAttribute("disabled")).toBe(false);
  });

  it("reads Saved, and cannot be pressed, with nothing to save", () => {
    mount(false);
    expect(screen.getByRole("button", { name: "Saved" }).hasAttribute("disabled")).toBe(true);
  });

  it("opens Share as a menu, runs an item, and gives the focus back on Escape", async () => {
    const user = userEvent.setup();
    const actions = mount();
    const share = screen.getByRole("button", { name: "Share" });

    await user.click(share);
    expect(screen.getAllByRole("menuitem").map((m) => m.textContent)).toEqual([
      "Copy code",
      "Paste code",
      "Export",
      "Import",
    ]);
    await user.click(screen.getByRole("menuitem", { name: "Export" }));
    expect(actions.exportRoute).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).toBeNull();

    await user.click(share);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(share);
  });
});
