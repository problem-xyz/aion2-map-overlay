/**
 * The pets tool: the checklist of a map's pets, each at its level, and the pets picked to be drawn
 * over the game -- no more than five of a map's, each in its colour.
 */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Settings } from "@/shared/backend/contract";
import { I18nProvider } from "@/shared/i18n";

import { petsOf } from "./lib/pets";
import PetsPage from "./PetsPage";

const change = vi.hoisted(() => vi.fn());
const state = vi.hoisted(() => ({ current: {} }));

vi.mock("@/shared/backend/BackendProvider", () => ({
  useBackendState: (select: (s: unknown) => unknown) => select(state.current),
}));

vi.mock("@/shared/backend/useSettingsPatch", () => ({
  useSettingsPatch: () => change,
}));

const ALTGARD = petsOf("altgard");
const first = ALTGARD[0]!;
const second = ALTGARD[1]!;

function mount(settings: Partial<Settings> = {}) {
  state.current = {
    settings: { show_pets: false, pets: [], pet_levels: {}, ...settings },
    maps: [
      { id: "altgard", label: "Altgard" },
      { id: "verteron", label: "Verteron" },
    ],
    routes: [{ id: "r", map: "altgard" }],
    route: "r",
  };
  render(
    <I18nProvider initial="en">
      <PetsPage />
    </I18nProvider>,
  );
}

function row(name: string): HTMLElement {
  const list = screen.getByRole("list", { name: "Pets on Altgard" });
  const item = within(list)
    .getAllByRole("listitem")
    .find((li) => li.querySelector(".pe-row-name")?.textContent === name);
  if (!item) throw new Error(`no row for ${name}`);
  return item;
}

beforeEach(() => {
  change.mockReset();
  window.localStorage.clear();
});

describe("PetsPage", () => {
  it("lists the route's map's pets, and counts those collected", () => {
    mount({ pet_levels: { [`altgard:${first.id}`]: 1, [`verteron:${second.id}`]: 3 } });

    expect(
      within(screen.getByRole("list", { name: "Pets on Altgard" })).getAllByRole("listitem"),
    ).toHaveLength(108);
    expect(screen.getByText("1")).toBeTruthy();
    expect(screen.getByText("/108")).toBeTruthy();
  });

  it("sets a level, and takes the one it is at back", () => {
    mount({ pet_levels: { [`altgard:${first.id}`]: 2 } });

    fireEvent.click(within(row(first.name)).getByRole("button", { name: "Level 3: 75 souls" }));
    expect(change).toHaveBeenLastCalledWith("pet_levels", { [`altgard:${first.id}`]: 3 });

    fireEvent.click(within(row(first.name)).getByRole("button", { name: "Level 2: 25 souls" }));
    expect(change).toHaveBeenLastCalledWith("pet_levels", { [`altgard:${first.id}`]: 1 });
  });

  it("picking a pet draws it, and turns the switch on", () => {
    mount();

    fireEvent.click(
      within(row(first.name)).getByRole("button", { name: `Show ${first.name} on the map` }),
    );

    expect(change).toHaveBeenCalledWith("pets", [first.id]);
    expect(change).toHaveBeenCalledWith("show_pets", true);
  });

  it("a pet brought to the last level is no longer drawn", () => {
    mount({ show_pets: true, pets: [first.id, second.id] });

    fireEvent.click(within(row(first.name)).getByRole("button", { name: "Level 3: 75 souls" }));

    expect(change).toHaveBeenCalledWith("pets", [second.id]);
  });

  it("offers no more once five of the map's are picked", () => {
    const five = ALTGARD.slice(0, 5).map((p) => p.id);
    mount({ show_pets: true, pets: five });

    const sixth = ALTGARD[5]!;
    const button = within(row(sixth.name)).getByRole<HTMLButtonElement>("button", {
      name: /Up to 5 pets at a time/,
    });
    expect(button.disabled).toBe(true);
    expect(screen.getByRole("list", { name: "Pets shown on the map" }).children).toHaveLength(5);
  });

  it("finds a pet by the name of one of its monsters", () => {
    mount();
    const monster = second.monsters[0]!.name;

    fireEvent.change(screen.getByPlaceholderText("Find a pet or monster"), {
      target: { value: monster },
    });

    expect(row(second.name)).toBeTruthy();
    expect(
      within(screen.getByRole("list", { name: "Pets on Altgard" })).getAllByRole("listitem").length,
    ).toBeLessThan(108);
  });

  it("shows the other map's pets when it is chosen", () => {
    mount();

    fireEvent.click(screen.getByRole("radio", { name: "Verteron" }));

    expect(
      within(screen.getByRole("list", { name: "Pets on Verteron" })).getAllByRole("listitem"),
    ).toHaveLength(113);
  });
});
