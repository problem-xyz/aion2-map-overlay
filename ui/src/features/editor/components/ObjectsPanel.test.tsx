/**
 * The map's objects in the editor: a group folds its children away and back, and each map keeps
 * which of its groups are folded.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import type { MapInfo, ObjectSet } from "@/shared/backend/contract";

import { buildIndex } from "../lib/objectsIndex";
import { EditorWrap, stubActions, stubState } from "../testing";

import ObjectsPanel from "./ObjectsPanel";

const SET: ObjectSet = {
  file: "altgard.json",
  mapName: "Altgard",
  categories: [
    { id: "gathering", name: "Gathering", parentId: null, color: "#8f99ad" },
    { id: "gathering-odyle", name: "Odyle", parentId: "gathering", color: "#33cc66" },
    { id: "gathering-ruby", name: "Ruby", parentId: "gathering", color: "#cc3344" },
    { id: "tp", name: "Teleports", parentId: null, color: "#ff0044" },
  ],
  nodes: [
    { c: "gathering-odyle", x: 10, y: 10, t: "Odyle", d: "" },
    { c: "gathering-ruby", x: 20, y: 20, t: "Ruby", d: "" },
    { c: "tp", x: 30, y: 30, t: "Teleport", d: "" },
  ],
};

function mapMeta(id: string): MapInfo {
  return {
    id,
    label: id,
    size: [100, 100],
    thumb: "",
    tiles: { ready: true, zMax: 2, tile: 256 },
    objects: [{ file: SET.file, mapName: SET.mapName, nodes: SET.nodes.length }],
  };
}

function mount(mapId = "altgard") {
  return render(
    <EditorWrap
      state={stubState({ mapMeta: mapMeta(mapId), objects: buildIndex([SET], [100, 100]) })}
      actions={stubActions()}
    >
      <ObjectsPanel />
    </EditorWrap>,
  );
}

beforeEach(() => window.localStorage.clear());

describe("ObjectsPanel", () => {
  it("shows a group's children until it is folded, and again once unfolded", () => {
    mount();
    expect(screen.getByText("Odyle")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Fold Gathering" }));
    expect(screen.queryByText("Odyle")).toBeNull();
    expect(screen.getByText("Teleports")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Unfold Gathering" }));
    expect(screen.getByText("Ruby")).toBeTruthy();
  });

  it("offers no fold for a category without children", () => {
    mount();
    expect(screen.queryByRole("button", { name: "Fold Teleports" })).toBeNull();
  });

  it("keeps the folds of each map apart, across openings", () => {
    const first = mount("altgard");
    fireEvent.click(screen.getByRole("button", { name: "Fold Gathering" }));
    first.unmount();

    const again = mount("altgard");
    expect(screen.queryByText("Odyle")).toBeNull();
    again.unmount();

    mount("verteron");
    expect(screen.getByText("Odyle")).toBeTruthy();
  });
});
