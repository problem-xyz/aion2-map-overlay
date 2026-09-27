/**
 * The route view in the editor: the overlay's choices less "steps", since the editor always
 * draws every point, and the count of steps ahead only where it changes what is drawn.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SettingsSchema } from "@/shared/backend/contract";

import { EditorWrap, stubActions, stubState } from "../testing";

import RouteViewPanel from "./RouteViewPanel";

const SCHEMA: SettingsSchema = {
  editor_opacity: { type: "float", default: 1, min: 0.1, max: 1 },
  editor_route_ahead: { type: "int", default: 3, min: 1, max: 10 },
};

const change = vi.hoisted(() => vi.fn());

vi.mock("@/shared/backend/BackendProvider", () => ({
  useBackendState: (select: (s: unknown) => unknown) => select({ settingsSchema: SCHEMA }),
}));

vi.mock("@/shared/backend/useSettingsPatch", () => ({
  useSettingsPatch: () => change,
}));

function mount(mode: "dim" | "all") {
  render(
    <EditorWrap state={stubState({ view: { mode, ahead: 3, opacity: 1 } })} actions={stubActions()}>
      <RouteViewPanel />
    </EditorWrap>,
  );
}

describe("RouteViewPanel", () => {
  it("offers the whole route faded or in full, and no steps-only view", () => {
    mount("dim");

    const radios = screen.getAllByRole("radio").map((r) => r.textContent);
    expect(radios).toEqual(["All, faded", "All"]);
  });

  it("shows the steps ahead only while the route fades away from the selected point", () => {
    mount("dim");
    expect(screen.getByRole("slider", { name: "Steps ahead" })).toBeDefined();
  });

  it("has no steps ahead to count while the whole route is drawn in full", () => {
    mount("all");
    expect(screen.queryByRole("slider", { name: "Steps ahead" })).toBeNull();
  });

  it("saves a choice as the editor's own setting, not the overlay's", async () => {
    const user = userEvent.setup();
    mount("dim");

    await user.click(screen.getByRole("radio", { name: "All" }));

    expect(change).toHaveBeenCalledWith("editor_route_view", "all");
  });
});
