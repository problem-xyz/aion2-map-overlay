// Tests for the map objects index: percent-to-pixel conversion, per-file category namespacing,
// the grid that backs nearest(), the category tree and the helpers around them.

import { describe, expect, it } from "vitest";

import type { ObjectNode, ObjectSet } from "@/shared/backend/contract";

import { buildIndex, categoryTree, defaultVisibility, objectLabel } from "./objectsIndex";
import { MARKER_COLORS } from "./palette";

/** Deliberately not square: a width/height mix-up has to surface as a failure. */
const SIZE: [number, number] = [1000, 500];

/** The colour Python writes for a category that has none of its own. */
const NEUTRAL = "#8f99ad";

/** Unwraps a value the test expects to exist: a missing one has to fail loudly, not silently. */
function must<T>(value: T | null | undefined): T {
  if (value === null || value === undefined) throw new Error("expected a value, got none");
  return value;
}

/** A node placed by its pixel position on SIZE, because the file format stores percentages. */
function at(c: string, xPx: number, yPx: number, t = "point", d = ""): ObjectNode {
  return { c, x: (xPx / SIZE[0]) * 100, y: (yPx / SIZE[1]) * 100, t, d };
}

function repeat(c: string, n: number): ObjectNode[] {
  return Array.from({ length: n }, () => at(c, 10, 10));
}

describe("buildIndex", () => {
  const sets: ObjectSet[] = [
    {
      file: "altgard.json",
      mapName: "altgard",
      categories: [
        { id: "tp", name: "Teleports", parentId: null, color: "#ff0044" },
        { id: "ore", name: "Ore", parentId: null, color: "#00ccff" },
      ],
      nodes: [
        { c: "tp", x: 25, y: 80, t: "Obelisk", d: "north gate" },
        { c: "tp", x: 10, y: 10, t: "Obelisk", d: "" },
        { c: "ore", x: 50, y: 50, t: "Vein", d: "" },
        { c: "ghost", x: 5, y: 5, t: "Nothing", d: "" },
      ],
    },
    {
      file: "eltnen.json",
      mapName: "eltnen",
      categories: [{ id: "tp", name: "Teleports", parentId: null, color: "#22ff88" }],
      nodes: [{ c: "tp", x: 60, y: 20, t: "Obelisk", d: "" }],
    },
  ];

  it("scales a node's percentages by the map width and height separately", () => {
    const point = must(buildIndex(sets, SIZE).points[0]);
    expect(point.x).toBeCloseTo(250, 6);
    expect(point.y).toBeCloseTo(400, 6);
  });

  it("namespaces category ids per file so two sets can share a raw id", () => {
    const index = buildIndex(sets, SIZE);
    expect(index.categories.map((c) => c.id)).toEqual([
      "altgard.json::tp",
      "altgard.json::ore",
      "eltnen.json::tp",
    ]);
    expect(must(index.byId.get("altgard.json::tp")).count).toBe(2);
    expect(must(index.byId.get("eltnen.json::tp")).count).toBe(1);
  });

  it("counts the nodes of every category", () => {
    const index = buildIndex(sets, SIZE);
    expect(must(index.byId.get("altgard.json::ore")).count).toBe(1);
    expect(index.points).toHaveLength(4);
  });

  it("drops a node whose category is not declared, without counting it anywhere", () => {
    const index = buildIndex(sets, SIZE);
    expect(index.points.some((p) => p.title === "Nothing")).toBe(false);
    expect(index.categories.reduce((sum, c) => sum + c.count, 0)).toBe(index.points.length);
  });

  it("drops a node whose category id only exists in another file", () => {
    const index = buildIndex(
      [
        {
          file: "a.json",
          mapName: "m",
          categories: [{ id: "tp", name: "Teleports", parentId: null, color: "#ff0044" }],
          nodes: [],
        },
        {
          file: "b.json",
          mapName: "m",
          categories: [],
          nodes: [{ c: "tp", x: 50, y: 50, t: "Stray", d: "" }],
        },
      ],
      SIZE,
    );
    expect(index.points).toHaveLength(0);
    expect(must(index.byId.get("a.json::tp")).count).toBe(0);
  });

  it("is empty only when no point survived", () => {
    const declaredOnly: ObjectSet[] = [
      {
        file: "a.json",
        mapName: "m",
        categories: [{ id: "tp", name: "Teleports", parentId: null, color: "#ff0044" }],
        nodes: [{ c: "nope", x: 1, y: 1, t: "Stray", d: "" }],
      },
    ];
    expect(buildIndex(declaredOnly, SIZE).empty).toBe(true);
    expect(buildIndex(sets, SIZE).empty).toBe(false);
  });

  it("tolerates a missing set list", () => {
    for (const none of [null, undefined]) {
      const index = buildIndex(none, SIZE);
      expect(index.empty).toBe(true);
      expect(index.categories).toHaveLength(0);
      expect(index.points).toHaveLength(0);
      expect(index.nearest(0, 0, 1000)).toBeNull();
    }
  });
});

describe("buildIndex colour inheritance", () => {
  const sets: ObjectSet[] = [
    {
      file: "color.json",
      mapName: "m",
      categories: [
        { id: "tp", name: "Teleports", parentId: null, color: "#ff0044" },
        { id: "tp-in", name: "Inbound", parentId: "tp", color: NEUTRAL },
        { id: "tp-out", name: "Outbound", parentId: "tp", color: "#00ccff" },
        { id: "solo", name: "Solo", parentId: null, color: NEUTRAL },
      ],
      nodes: [],
    },
  ];
  const byId = buildIndex(sets, SIZE).byId;

  it("gives a neutral child the colour of its parent", () => {
    expect(must(byId.get("color.json::tp-in")).color).toBe("#ff0044");
  });

  it("keeps a child colour that is not the neutral one", () => {
    expect(must(byId.get("color.json::tp-out")).color).toBe("#00ccff");
  });

  it("keeps the neutral colour on a root that has no parent", () => {
    expect(must(byId.get("color.json::solo")).color).toBe(NEUTRAL);
  });
});

describe("nearest", () => {
  const FILE = "poi.json";
  const GATHER = `${FILE}::gather`;
  const QUEST = `${FILE}::quest`;

  function indexOf(nodes: ObjectNode[]) {
    return buildIndex(
      [
        {
          file: FILE,
          mapName: "m",
          categories: [
            { id: "gather", name: "Gather", parentId: null, color: "#ff0044" },
            { id: "quest", name: "Quest", parentId: null, color: "#00ccff" },
          ],
          nodes,
        },
      ],
      SIZE,
    );
  }

  it("returns the closest point when several are inside the radius", () => {
    const index = indexOf([
      at("gather", 240, 200, "middle"),
      at("gather", 210, 200, "closest"),
      at("gather", 260, 200, "farthest"),
    ]);
    expect(must(index.nearest(200, 200, 60)).title).toBe("closest");
  });

  it("returns null when every point is outside the radius", () => {
    const index = indexOf([at("gather", 260, 200, "out of reach")]);
    expect(index.nearest(200, 200, 40)).toBeNull();
  });

  it("skips a point whose category is hidden even when it is the closest", () => {
    const index = indexOf([
      at("quest", 205, 200, "hidden one"),
      at("gather", 240, 200, "visible one"),
    ]);
    const found = must(index.nearest(200, 200, 60, { [GATHER]: true, [QUEST]: false }));
    expect(found.title).toBe("visible one");
  });

  it("treats a category missing from the visibility map as hidden", () => {
    const index = indexOf([at("gather", 205, 200, "lone point")]);
    expect(index.nearest(200, 200, 60, {})).toBeNull();
  });

  it("considers every category when no visibility map is given", () => {
    const index = indexOf([at("quest", 205, 200, "quest point")]);
    expect(must(index.nearest(200, 200, 60)).title).toBe("quest point");
    expect(must(index.nearest(200, 200, 60, null)).title).toBe("quest point");
  });

  it("counts a point that lies exactly on the radius", () => {
    // The radius is measured off the built index rather than assumed, because the file format
    // stores percentages and the round trip back to pixels is not bit-exact.
    const index = indexOf([at("gather", 260, 200, "on the line")]);
    const point = must(index.points[0]);
    const exact = Math.hypot(point.x - 200, point.y - 200);

    expect(must(index.nearest(200, 200, exact)).title).toBe("on the line");
    expect(index.nearest(200, 200, exact - 1e-9)).toBeNull();
  });

  it("returns the later point when two sit at the same distance", () => {
    // Arbitrary, but pinned: `d <= bestDist` keeps the last equal hit, while
    // geometry.nearestSegment keeps the first. Changing either should be a decision.
    const index = indexOf([at("gather", 220, 200, "earlier"), at("gather", 220, 200, "later")]);

    expect(must(index.nearest(200, 200, 60)).title).toBe("later");
  });

  it("finds a point that sits in a neighbouring grid cell", () => {
    // Cells are 96 map pixels wide, so (90, 100) and the query at (100, 100) straddle a boundary.
    const index = indexOf([at("gather", 90, 100, "across the line")]);
    expect(must(index.nearest(100, 100, 30)).title).toBe("across the line");
  });

  it("widens the cell search when the radius spans more than one cell", () => {
    // 150 pixels away is two cells away, so a single ring of neighbours would miss it.
    const index = indexOf([at("gather", 198, 48, "two cells away")]);
    expect(must(index.nearest(48, 48, 200)).title).toBe("two cells away");
    expect(index.nearest(48, 48, 100)).toBeNull();
  });
});

describe("categoryTree", () => {
  const sets: ObjectSet[] = [
    {
      file: "tree.json",
      mapName: "m",
      categories: [
        { id: "gather", name: "Gather", parentId: null, color: "#11aa11" },
        { id: "herbs", name: "Herbs", parentId: "gather", color: "#11aa11" },
        { id: "ore", name: "Ore", parentId: "gather", color: "#11aa11" },
        { id: "teleport", name: "Teleports", parentId: null, color: "#ff0044" },
        { id: "lost", name: "Lost", parentId: "nowhere", color: "#00ccff" },
        { id: "silent", name: "Silent", parentId: null, color: "#00ccff" },
        { id: "hollow", name: "Hollow", parentId: null, color: "#00ccff" },
        { id: "kid", name: "Kid", parentId: "hollow", color: "#00ccff" },
      ],
      nodes: [
        ...repeat("gather", 1),
        ...repeat("herbs", 2),
        ...repeat("ore", 3),
        ...repeat("teleport", 4),
        ...repeat("lost", 1),
        ...repeat("kid", 2),
      ],
    },
  ];
  const tree = categoryTree(buildIndex(sets, SIZE));

  it("keeps roots at the top level and nests children under them", () => {
    expect(tree.map((c) => c.id)).toEqual([
      "tree.json::gather",
      "tree.json::teleport",
      "tree.json::lost",
      "tree.json::hollow",
    ]);
    expect(must(tree[0]).children.map((c) => c.id)).toEqual(["tree.json::herbs", "tree.json::ore"]);
    expect(must(tree[1]).children).toHaveLength(0);
  });

  it("adds the children's counts to the total of their root", () => {
    const gather = must(tree[0]);

    expect(gather.count).toBe(1);
    expect(gather.total).toBe(6);
    expect(gather.children.map((c) => c.total)).toEqual([2, 3]);
  });

  it("treats a category whose parent is unknown as a root", () => {
    const lost = must(tree.find((c) => c.id === "tree.json::lost"));
    expect(lost.total).toBe(1);
  });

  it("keeps a root that only has points through its children", () => {
    const hollow = must(tree.find((c) => c.id === "tree.json::hollow"));
    expect(hollow.count).toBe(0);
    expect(hollow.total).toBe(2);
  });

  it("leaves out a root with no points of its own or below it", () => {
    expect(tree.some((c) => c.id === "tree.json::silent")).toBe(false);
  });
});

describe("defaultVisibility", () => {
  const sets: ObjectSet[] = [
    {
      file: "big.json",
      mapName: "m",
      categories: [
        { id: "small", name: "Small", parentId: null, color: "#ff0044" },
        { id: "edge", name: "Edge", parentId: null, color: "#ff0044" },
        { id: "over", name: "Over", parentId: null, color: "#ff0044" },
        { id: "none", name: "None", parentId: null, color: "#ff0044" },
      ],
      nodes: [...repeat("small", 5), ...repeat("edge", 200), ...repeat("over", 201)],
    },
  ];
  const visible = defaultVisibility(buildIndex(sets, SIZE));

  it("shows a small category", () => {
    expect(visible["big.json::small"]).toBe(true);
  });

  it("shows a large category too", () => {
    expect(visible["big.json::edge"]).toBe(true);
    expect(visible["big.json::over"]).toBe(true);
  });

  it("hides a category with no points at all", () => {
    expect(visible["big.json::none"]).toBe(false);
  });
});

describe("objectLabel", () => {
  it("joins the title and the description with an em dash", () => {
    expect(objectLabel({ title: "Empyrean Trace", description: "SafeHaven" })).toBe(
      "Empyrean Trace — SafeHaven",
    );
  });

  it("returns the title alone when there is no description", () => {
    expect(objectLabel({ title: "Teleports", description: "" })).toBe("Teleports");
  });

  it("returns the description alone when there is no title", () => {
    expect(objectLabel({ title: "", description: "SafeHaven" })).toBe("SafeHaven");
  });

  it("returns an empty string when both parts are missing", () => {
    expect(objectLabel({})).toBe("");
    expect(objectLabel({ title: "   ", description: "  " })).toBe("");
  });

  it("trims the whitespace around both parts", () => {
    expect(objectLabel({ title: "  Empyrean Trace ", description: " SafeHaven  " })).toBe(
      "Empyrean Trace — SafeHaven",
    );
  });
});

describe("buildIndex, the owner's cut of the sets", () => {
  const sets: ObjectSet[] = [
    {
      file: "altgard.json",
      mapName: "altgard",
      categories: [
        { id: "locations", name: "Locations", parentId: null, color: "#22c55e" },
        { id: "teleports", name: "Teleports", parentId: "locations", color: "#16a34a" },
        { id: "seals", name: "Seals", parentId: "locations", color: "#22c55e" },
        { id: "villages", name: "Villages", parentId: "locations", color: "#15803d" },
        { id: "occupation", name: "Occupation", parentId: "locations", color: "#86efac" },
        { id: "battlefields", name: "Battlefields", parentId: "locations", color: "#4ade80" },
        { id: "empyrean-trace-altgard", name: "Empyrean Trace", parentId: null, color: "#a78bfa" },
        { id: "hidden-cube-altgard", name: "Hidden Cube", parentId: null, color: "#eab308" },
      ],
      nodes: [
        at("teleports", 10, 10),
        at("seals", 20, 20),
        at("villages", 30, 30),
        at("occupation", 40, 40),
        at("battlefields", 50, 50),
        at("empyrean-trace-altgard", 60, 60),
      ],
    },
  ];

  it("leaves villages, occupation and battlefields out, points and all", () => {
    const index = buildIndex(sets, SIZE);

    expect(index.categories.map((c) => c.name)).toEqual([
      "Locations",
      "Teleports",
      "Seals",
      "Empyrean Trace",
      "Hidden Cube",
    ]);
    expect(index.points).toHaveLength(3);
    // nor can anything snap to them
    expect(index.nearest(30, 30, 5)).toBeNull();
  });

  it("gives the teleports, seals, Empyrean Traces and hidden cubes their icons, on any map", () => {
    const index = buildIndex(sets, SIZE);
    const icon = (name: string) => index.categories.find((c) => c.name === name)?.icon;

    expect(icon("Teleports")).toBe("teleport");
    expect(icon("Seals")).toBe("seal");
    expect(icon("Empyrean Trace")).toBe("trace");
    expect(icon("Hidden Cube")).toBe("cube");
    expect(icon("Locations")).toBeNull();
  });

  it("colours those categories from the marker palette, after their icons", () => {
    const index = buildIndex(sets, SIZE);
    const color = (name: string) => index.categories.find((c) => c.name === name)?.color;
    const swatch = (key: string) => MARKER_COLORS.find((c) => c.nameKey === key)?.value;

    expect(color("Teleports")).toBe(swatch("editor.colors.purple"));
    expect(color("Seals")).toBe(swatch("editor.colors.blue"));
    expect(color("Empyrean Trace")).toBe(swatch("editor.colors.white"));
    expect(color("Hidden Cube")).toBe(swatch("editor.colors.red"));
    // a category with no icon keeps the set's own colour
    expect(color("Locations")).toBe("#22c55e");
  });
});

describe("buildIndex, the Elyos teleports", () => {
  it("marks the teleports of Verteron, an Elyos map, with the blue winged figure", () => {
    const set = (mapName: string): ObjectSet => ({
      file: `${mapName.toLowerCase()}.json`,
      mapName,
      categories: [{ id: "teleports", name: "Teleports", parentId: null, color: "#16a34a" }],
      nodes: [at("teleports", 10, 10)],
    });

    // the sets spell the names capitalised
    expect(buildIndex([set("Verteron")], SIZE).categories[0]?.icon).toBe("teleportElyos");
    expect(buildIndex([set("Altgard")], SIZE).categories[0]?.icon).toBe("teleport");
  });
});
