/**
 * The object under a route point: what the panel's list of points draws beside the number. A
 * point counts as on an object only where the editor would have snapped it there, within a map
 * pixel, and only an object the game gives an icon of its own brings one.
 */

import { describe, expect, it } from "vitest";

import type { ObjectSet } from "@/shared/backend/contract";

import { iconFor, iconsUnder } from "./objectMarks";

const SIZE: [number, number] = [1000, 500];

function set(mapName: string, nodes: [string, number, number][]): ObjectSet {
  return {
    file: `${mapName}.json`,
    mapName,
    categories: ["teleports", "seals", "empyrean-trace-altgard", "gathering"].map((id) => ({
      id,
      name: id,
      color: "#888888",
      parentId: null,
    })),
    nodes: nodes.map(([c, x, y]) => ({ c, x, y, t: "", d: "" })),
  };
}

describe("iconFor", () => {
  it("gives the Elyos teleports their own figure, whatever the map name's case", () => {
    expect(iconFor("teleports", "Verteron")).toBe("teleportElyos");
    expect(iconFor("teleports", "Altgard")).toBe("teleport");
    expect(iconFor("empyrean-trace-altgard")).toBe("trace");
    expect(iconFor("hidden-cube-verteron")).toBe("cube");
    expect(iconFor("gathering")).toBeNull();
  });
});

describe("iconsUnder", () => {
  // percent of the map: (10%, 20%) is (100, 100) in pixels on a 1000 x 500 map
  const sets = [
    set("Altgard", [
      ["teleports", 10, 20],
      ["seals", 50, 50],
      ["gathering", 80, 80],
    ]),
  ];

  it("finds the object a point was snapped onto, in the points' order", () => {
    const points = [
      { x: 250, y: 250 }, // nothing there
      { x: 500, y: 250.6 }, // the seal, within a pixel
      { x: 100, y: 100 }, // the teleport, exactly
    ];
    expect(iconsUnder(sets, SIZE, points)).toEqual([null, "seal", "teleport"]);
  });

  it("does not count a point a few pixels off as on the object", () => {
    expect(iconsUnder(sets, SIZE, [{ x: 103, y: 100 }])).toEqual([null]);
  });

  it("gives nothing for an object the game draws as a plain dot", () => {
    expect(iconsUnder(sets, SIZE, [{ x: 800, y: 400 }])).toEqual([null]);
  });

  it("gives nothing for a point with no place, from a backend before api 11", () => {
    expect(iconsUnder(sets, SIZE, [{ x: Number.NaN, y: Number.NaN }])).toEqual([null]);
  });
});
