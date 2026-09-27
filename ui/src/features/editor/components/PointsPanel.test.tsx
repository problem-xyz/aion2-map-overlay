/**
 * The points list: what it announces, where the tab lands, and what the keys do to the order.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";

import { buildIndex } from "../lib/objectsIndex";
import type { EditorMarker } from "../lib/routeDoc";
import { EditorWrap, stubActions, stubState } from "../testing";

import PointsPanel, { INSPECTOR_TEXT_ID } from "./PointsPanel";

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

const MARKERS: EditorMarker[] = [
  { id: 1, x: 10, y: 10, text: "gate" },
  { id: 2, x: 20, y: 20, text: "" },
  { id: 3, x: 30, y: 30, text: "boss", color: "#4fd1c5" },
];

function mount(selectedId: number | null = null) {
  const actions = stubActions();
  render(
    <EditorWrap state={stubState({ markers: MARKERS, selectedId })} actions={actions}>
      <PointsPanel />
    </EditorWrap>,
  );
  return actions;
}

const rows = () => screen.getAllByRole("option");

describe("PointsPanel", () => {
  it("is a listbox of every point, the selected one marked, with a placeholder for no label", () => {
    mount(3);

    expect(screen.getByRole("listbox", { name: "Route points" })).toBeDefined();
    expect(rows()).toHaveLength(3);
    expect(screen.getByRole("option", { selected: true })).toBe(rows()[2]);
    expect(rows()[1]?.textContent).toContain("What to do here");
  });

  it("lays the living sheen under the selected row alone, hidden from a screen reader", () => {
    mount(2);
    const sheens = document.querySelectorAll(".ui-sheen");
    expect(sheens).toHaveLength(1);
    expect(screen.getByRole("option", { selected: true }).contains(sheens[0] ?? null)).toBe(true);
    expect(sheens[0]?.getAttribute("aria-hidden")).toBe("true");
  });

  it("puts one row in the tab order: the selected one, else the first", () => {
    mount(2);

    expect(rows().map((r) => r.tabIndex)).toEqual([-1, 0, -1]);
  });

  it("selects on a click and on Enter", async () => {
    const user = userEvent.setup();
    const actions = mount();

    await user.click(screen.getByText("gate"));
    expect(actions.focusMarker).toHaveBeenLastCalledWith(1);

    rows()[2]?.focus();
    await user.keyboard("{Enter}");
    expect(actions.focusMarker).toHaveBeenLastCalledWith(3);
  });

  it("hands a click on to the label field, and keeps Enter in the list", async () => {
    const user = userEvent.setup();
    const actions = stubActions();
    render(
      <EditorWrap state={stubState({ markers: MARKERS })} actions={actions}>
        <PointsPanel />
        {/* the inspector's field, which the real editor renders beside the list */}
        <textarea id={INSPECTOR_TEXT_ID} aria-label="label" />
      </EditorWrap>,
    );
    const field = screen.getByRole("textbox", { name: "label" });

    await user.click(screen.getByText("gate"));
    await new Promise((r) => requestAnimationFrame(r));
    expect(document.activeElement).toBe(field);

    rows()[2]?.focus();
    await user.keyboard("{Enter}");
    await new Promise((r) => requestAnimationFrame(r));
    expect(document.activeElement).toBe(rows()[2]);
  });

  it("moves a point along the route with Alt+Up and Alt+Down", async () => {
    const user = userEvent.setup();
    const actions = mount();

    rows()[1]?.focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");
    expect(actions.moveMarkerTo).toHaveBeenLastCalledWith(2, 0);
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(actions.moveMarkerTo).toHaveBeenLastCalledWith(2, 2);
  });

  it("walks the rows with the arrows and deletes the focused one with Delete", async () => {
    const user = userEvent.setup();
    const actions = mount();

    rows()[0]?.focus();
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(rows()[1]);
    await user.keyboard("{Delete}");
    expect(actions.deleteMarker).toHaveBeenCalledWith(2);
  });

  it("finds points by label or number, and has no grips while filtered", async () => {
    const user = userEvent.setup();
    mount();

    await user.type(screen.getByRole("searchbox", { name: "Find a point" }), "bos");
    expect(rows()).toHaveLength(1);
    expect(rows()[0]?.textContent).toContain("boss");

    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "zzz");
    expect(screen.getByText("No point matches “zzz”.")).toBeDefined();
  });

  it("clears the search from its own button, which shows only while there is one", async () => {
    const user = userEvent.setup();
    mount();
    const all = rows().length;
    const clear = () => screen.queryByRole("button", { name: "Clear the search" });

    expect(clear()).toBeNull();
    await user.type(screen.getByRole("searchbox"), "bos");
    await user.click(clear() as HTMLElement);

    expect(screen.getByRole("searchbox")).toHaveProperty("value", "");
    expect(document.activeElement).toBe(screen.getByRole("searchbox"));
    expect(rows()).toHaveLength(all);
    expect(clear()).toBeNull();
  });

  it("shows the icon of the object a point sits on, and nothing for a point on none", () => {
    // a teleport under "gate" (10, 10), on a 100 x 100 map: the set stores percentages
    const objects = buildIndex(
      [
        {
          file: "altgard.json",
          mapName: "altgard",
          categories: [{ id: "teleports", name: "Teleports", parentId: null, color: "#16a34a" }],
          nodes: [{ c: "teleports", x: 10, y: 10, t: "Obelisk", d: "" }],
        },
      ],
      [100, 100],
    );
    render(
      <EditorWrap state={stubState({ markers: MARKERS, objects })} actions={stubActions()}>
        <PointsPanel />
      </EditorWrap>,
    );

    expect(rows()[0]?.querySelector("svg.ed-row-icon")).not.toBeNull();
    expect(rows()[1]?.querySelector("svg.ed-row-icon")).toBeNull();
  });

  it("shows a point's own quest star, with no object under it", () => {
    render(
      <EditorWrap
        state={stubState({ markers: [{ id: 1, x: 10, y: 10, text: "elder", icon: "main" }] })}
        actions={stubActions()}
      >
        <PointsPanel />
      </EditorWrap>,
    );

    expect(rows()[0]?.querySelector("svg.ed-row-icon")).not.toBeNull();
  });
});
