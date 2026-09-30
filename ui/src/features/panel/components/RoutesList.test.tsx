/**
 * The route row: the part that selects a route is a real button, and the edit and
 * delete buttons sit beside it rather than inside it. What is pinned here is exactly that --
 * that no button nests inside another, that a pointer still selects a route by clicking the row,
 * that the active row says so with aria-current, and that every icon button has a name that
 * says which route it belongs to.
 *
 * Expected sentences come out of the shipped catalogue rather than being typed here: a literal
 * would duplicate locales/en.json and pin this week's wording instead of the key.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RouteInfo } from "@/shared/backend/contract";
import { I18nProvider, catalogs } from "@/shared/i18n";

import RoutesList, { type RoutesListProps } from "./RoutesList";

function en(key: string): string {
  const message = catalogs.get("en")?.get(key);
  if (typeof message !== "string") throw new Error(`no English message for ${key}`);
  return message;
}

function fill(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (whole, name: string) => {
    const value = params[name];
    return value === undefined ? whole : String(value);
  });
}

const ROUTES: RouteInfo[] = [
  { id: "a", label: "Aslan", map: "elyos", mapLabel: "Elyos", markers: 4, steps: 0, thumb: "" },
  { id: "b", label: "Beluslan", map: "asmo", mapLabel: "Asmo", markers: 7, steps: 2, thumb: "" },
];

function mount(props: Partial<RoutesListProps> = {}) {
  const handlers = {
    onSelect: vi.fn(),
    onEditor: vi.fn(),
    onNew: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onReorder: vi.fn(),
    onImport: vi.fn(),
    onPaste: vi.fn(),
    onOpenFolder: vi.fn(),
  };
  render(
    <I18nProvider initial="en">
      <RoutesList routes={ROUTES} active="b" {...handlers} {...props} />
    </I18nProvider>,
  );
  return handlers;
}

describe("RoutesList", () => {
  it("nests no button inside another", () => {
    mount();

    expect(document.querySelectorAll("button button")).toHaveLength(0);
    // one row button and two action buttons per route, plus editor, import, paste, new, folder
    expect(screen.getAllByRole("button")).toHaveLength(ROUTES.length * 3 + 5);
  });

  it("keeps the map picture out of the button, so a press cannot shrink it", () => {
    mount({ routes: ROUTES.map((r) => ({ ...r, thumb: "data:image/png;base64," })) });

    expect(document.querySelectorAll(".route > img")).toHaveLength(ROUTES.length);
    expect(document.querySelector(".pn-route-main img")).toBeNull();
  });

  it("opens the editor from the button over the list, the one E presses", async () => {
    const user = userEvent.setup();
    const handlers = mount();

    const editor = screen.getByRole("button", { name: /Editor/ });
    expect(editor.getAttribute("aria-keyshortcuts")).toBe("E");
    await user.click(editor);

    expect(handlers.onEditor).toHaveBeenCalledTimes(1);
  });

  it("selects the route when the row is clicked with a pointer", async () => {
    const user = userEvent.setup();
    const handlers = mount();

    await user.click(screen.getByText("Aslan"));

    expect(handlers.onSelect).toHaveBeenCalledTimes(1);
    expect(handlers.onSelect).toHaveBeenCalledWith("a");
  });

  it("selects the route from the keyboard", async () => {
    const user = userEvent.setup();
    const handlers = mount();

    screen.getByText("Aslan").closest("button")?.focus();
    await user.keyboard("{Enter}");

    expect(handlers.onSelect).toHaveBeenCalledWith("a");
  });

  it("marks only the active row with aria-current", () => {
    mount();

    const marked = screen
      .getAllByRole("button")
      .filter((button) => button.getAttribute("aria-current") !== null);

    expect(marked).toHaveLength(1);
    expect(marked[0]?.getAttribute("aria-current")).toBe("true");
    expect(marked[0]?.textContent).toContain("Beluslan");
  });

  it("names the edit and the delete button after their own route", () => {
    mount();

    for (const route of ROUTES) {
      const edit = fill(en("panel.routes.editNamed"), { label: route.label });
      const remove = fill(en("panel.routes.deleteNamed"), { label: route.label });
      expect(screen.getByRole("button", { name: edit })).toBeDefined();
      expect(screen.getByRole("button", { name: remove })).toBeDefined();
    }
  });

  it("keeps the tooltip on the action, not the route", () => {
    mount();

    const edit = fill(en("panel.routes.editNamed"), { label: "Aslan" });
    const button = screen.getByRole("button", { name: edit });

    expect(button.getAttribute("title")).toBe(en("panel.routes.editTip"));
    // the accessible-name algorithm falls back to `title`, so a getByRole(name) query alone
    // cannot tell a named button from one that only has a tooltip. This can.
    expect(button.getAttribute("aria-label")).toBe(edit);
  });

  it("does not select the route when an action button is pressed", async () => {
    const user = userEvent.setup();
    const handlers = mount();

    await user.click(
      screen.getByRole("button", {
        name: fill(en("panel.routes.editNamed"), { label: "Aslan" }),
      }),
    );

    expect(handlers.onEdit).toHaveBeenCalledWith("a");
    expect(handlers.onSelect).not.toHaveBeenCalled();
  });

  it("gives the row button a name built from the route, and hides the thumbnail from it", () => {
    mount();

    const rows = screen.getAllByRole("listitem");
    const first = rows[0];
    if (!first) throw new Error("no route row rendered");
    const main = within(first).getAllByRole("button")[0];

    expect(main?.textContent).toContain("Aslan");
    expect(main?.textContent).toContain("Elyos");
    // the thumbnail is decorative: it must not turn up as an image with a name of its own
    expect(within(first).queryByRole("img")).toBeNull();
  });

  it("shows the empty text instead of a list when there are no routes", () => {
    mount({ routes: [] });

    expect(screen.getByText(en("panel.routes.empty"))).toBeDefined();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });
});

const THREE: RouteInfo[] = [
  ...ROUTES,
  { id: "c", label: "Morheim", map: "asmo", mapLabel: "Asmo", markers: 3, steps: 0, thumb: "" },
];

function labels(): string[] {
  return screen
    .getAllByRole("listitem")
    .map((li) => li.querySelector(".route-label")?.textContent ?? "");
}

describe("RoutesList reordering", () => {
  // jsdom lays nothing out and captures no pointer: each tile is given a height, capture a no-op.
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockReturnValue(50);
    HTMLElement.prototype.setPointerCapture = vi.fn();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function row(label: string): HTMLElement {
    const li = screen.getByText(label).closest("li");
    if (!li) throw new Error(`no row for ${label}`);
    return li;
  }

  it("moves a dragged tile to where it is dropped, and does not select it", () => {
    const handlers = mount({ routes: THREE });

    fireEvent.pointerDown(row("Aslan"), { button: 0, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 60, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 112, pointerId: 1 });
    fireEvent.pointerUp(window, { clientY: 112, pointerId: 1 });
    fireEvent.click(screen.getByText("Aslan"));

    expect(handlers.onReorder).toHaveBeenCalledWith(["b", "c", "a"]);
    expect(handlers.onSelect).not.toHaveBeenCalled();
    // shown in the new order at once, not after the backend's round trip
    expect(labels()).toEqual(["Beluslan", "Morheim", "Aslan"]);
  });

  it("leaves a press that does not travel as a click", async () => {
    const user = userEvent.setup();
    const handlers = mount({ routes: THREE });

    fireEvent.pointerDown(row("Aslan"), { button: 0, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 12, pointerId: 1 });
    fireEvent.pointerUp(window, { clientY: 12, pointerId: 1 });
    await user.click(screen.getByText("Aslan"));

    expect(handlers.onReorder).not.toHaveBeenCalled();
    expect(handlers.onSelect).toHaveBeenCalledWith("a");
  });

  it("puts the tile back when Escape is pressed mid-drag", () => {
    const handlers = mount({ routes: THREE });

    fireEvent.pointerDown(row("Aslan"), { button: 0, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 112, pointerId: 1 });
    fireEvent.keyDown(window, { key: "Escape" });
    fireEvent.pointerUp(window, { clientY: 112, pointerId: 1 });

    expect(handlers.onReorder).not.toHaveBeenCalled();
    expect(labels()).toEqual(["Aslan", "Beluslan", "Morheim"]);
  });

  it("does not start a drag from the edit and delete buttons", () => {
    const handlers = mount({ routes: THREE });
    const edit = screen.getByRole("button", {
      name: fill(en("panel.routes.editNamed"), { label: "Aslan" }),
    });

    fireEvent.pointerDown(edit, { button: 0, clientY: 10, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 112, pointerId: 1 });
    fireEvent.pointerUp(window, { clientY: 112, pointerId: 1 });

    expect(handlers.onReorder).not.toHaveBeenCalled();
  });

  it("moves the focused tile with Alt and the arrows, and keeps the focus on it", async () => {
    const user = userEvent.setup();
    const handlers = mount({ routes: THREE });

    screen.getByText("Beluslan").closest("button")?.focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");

    expect(handlers.onReorder).toHaveBeenCalledWith(["b", "a", "c"]);
    expect(labels()).toEqual(["Beluslan", "Aslan", "Morheim"]);
    expect(document.activeElement?.textContent).toContain("Beluslan");

    await user.keyboard("{Alt>}{ArrowUp}{/Alt}"); // already first: nowhere to go
    expect(handlers.onReorder).toHaveBeenCalledTimes(1);
  });

  it("no longer counts the points with text", () => {
    mount();
    expect(screen.getByText(/Beluslan/).closest("button")?.textContent).not.toMatch(/text/);
  });
});

const SIDES: RouteInfo[] = [
  { ...(THREE[0] as RouteInfo), faction: "elyos", official: true },
  { ...(THREE[1] as RouteInfo), faction: "asmodian" },
  { ...(THREE[2] as RouteInfo), faction: "asmodian" },
];

describe("RoutesList filter", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("is offered only when the list has routes of both sides", () => {
    mount({ routes: SIDES.slice(1) });
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("shows one side's routes, and remembers the choice", async () => {
    const user = userEvent.setup();
    mount({ routes: SIDES });

    await user.click(screen.getByRole("radio", { name: en("panel.routes.filterAsmodian") }));

    expect(labels()).toEqual(["Beluslan", "Morheim"]);
    expect(window.localStorage.getItem("mo.panel.routeFilter")).toBe("asmodian");
  });

  it("moves a row among the shown ones and keeps the hidden ones in place", async () => {
    const user = userEvent.setup();
    const handlers = mount({ routes: SIDES });
    await user.click(screen.getByRole("radio", { name: en("panel.routes.filterAsmodian") }));

    screen.getByText("Morheim").closest("button")?.focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");

    expect(handlers.onReorder).toHaveBeenCalledWith(["a", "c", "b"]);
  });

  it("marks an official route", () => {
    mount({ routes: SIDES });

    const tags = document.querySelectorAll(".route-tag");
    expect(tags).toHaveLength(1);
    expect(tags[0]?.closest("li")?.textContent).toContain("Aslan");
  });
});
