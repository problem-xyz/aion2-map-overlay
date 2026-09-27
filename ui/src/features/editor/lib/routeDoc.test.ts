/**
 * The file format boundary. What matters here is not that the functions run, but that the
 * editor's `id` never reaches the file and that a document read from disk comes back out
 * of the editor byte for byte -- the dirty flag compares `JSON.stringify` output.
 */

import { describe, expect, it } from "vitest";

import type { RouteDoc } from "@/shared/backend/contract";

import { QUEST_COLOR } from "./palette";
import {
  DEFAULT_ROUTE_STYLE,
  ROUTE_FORMAT,
  ROUTE_VERSION,
  fromRouteDoc,
  markerWithIcon,
  type MarkerLike,
  stackOrder,
  type RouteDraftInput,
  stripMarkerIds,
  toRouteDoc,
  withMarkerIds,
} from "./routeDoc";

/**
 * The name an unnamed route falls back to. `toRouteDoc` takes it as an argument rather than
 * holding a constant, because on screen that word is translated; here it stands for whatever
 * `t("editor.unnamedRoute")` returned.
 */
const FALLBACK_NAME = "Route";

function draftOf(over: Partial<RouteDraftInput> = {}): RouteDraftInput {
  return {
    name: "Beluslan run",
    mapId: "beluslan",
    size: [8192, 8192],
    markers: [],
    style: { color: "#33aaff", width: 4 },
    ...over,
  };
}

/** Unwraps a value the test expects to exist: a missing one has to fail loudly, not silently. */
function must<T>(value: T | undefined): T {
  if (value === undefined) throw new Error("expected a value, got undefined");
  return value;
}

/** A document as it sits in a route file: mixed captions, one marker with its own colour. */
function storedDoc(): RouteDoc {
  return {
    format: ROUTE_FORMAT,
    version: ROUTE_VERSION,
    name: "Beluslan 40-45",
    map: "beluslan",
    mapSize: [8192, 8192],
    markers: [
      { x: 0.1, y: 0.2, text: "Start at the obelisk" },
      { x: 0.35, y: 0.42, text: "" },
      { x: 0.5, y: 0.5, text: "Elite camp", color: "#ff5555" },
    ],
    style: { color: "#33aaff", width: 4 },
  };
}

/**
 * The same document as written by a build that had no style field yet. The contract type says
 * the field is always there, so the key has to be removed rather than set to undefined.
 */
function docWithoutStyle(): RouteDoc {
  const doc = storedDoc();
  delete (doc as Partial<RouteDoc>).style;
  return doc;
}

describe("stripMarkerIds", () => {
  it("drops the id and keeps every other field, including an optional color", () => {
    const marker: MarkerLike = { x: 10, y: 20, text: "gate", color: "#123456", id: 7 };

    const stripped = must(stripMarkerIds([marker])[0]);

    expect(stripped).toEqual({ x: 10, y: 20, text: "gate", color: "#123456" });
    expect("id" in stripped).toBe(false);
  });

  it("preserves the key order of the remaining fields, whatever position the id held", () => {
    const idFirst: MarkerLike = { id: 3, x: 1, y: 2, text: "a", color: "#fff" };
    const idInTheMiddle: MarkerLike = { x: 1, id: 4, y: 2, text: "b" };

    const [first, second] = stripMarkerIds([idFirst, idInTheMiddle]);

    expect(Object.keys(must(first))).toEqual(["x", "y", "text", "color"]);
    expect(Object.keys(must(second))).toEqual(["x", "y", "text"]);
  });

  it("leaves a marker that never had an id unchanged in content", () => {
    const marker: MarkerLike = { x: 0.5, y: 0.25, text: "" };

    const stripped = must(stripMarkerIds([marker])[0]);

    expect(stripped).toEqual(marker);
    expect(Object.keys(stripped)).toEqual(["x", "y", "text"]);
  });

  it("returns new objects and mutates neither the input array nor its markers", () => {
    const marker: MarkerLike = { x: 1, y: 2, text: "a", id: 9 };
    const markers: MarkerLike[] = [marker];

    const [stripped] = stripMarkerIds(markers);

    expect(stripped).not.toBe(marker);
    expect(markers).toEqual([{ x: 1, y: 2, text: "a", id: 9 }]);
  });

  it("maps an empty list to an empty list", () => {
    expect(stripMarkerIds([])).toEqual([]);
  });
});

describe("stackOrder", () => {
  it("counts the earlier points on the same spot: a teleport the route comes back to", () => {
    const tp = { x: 10, y: 20, text: "" };
    const other = { x: 50, y: 60, text: "" };

    expect(stackOrder([tp, other, { ...tp }, other, { ...tp }])).toEqual([0, 0, 1, 1, 2]);
  });

  it("keeps points apart that are close but not on one spot", () => {
    expect(
      stackOrder([
        { x: 10, y: 20, text: "" },
        { x: 10.01, y: 20, text: "" },
      ]),
    ).toEqual([0, 0]);
  });
});

describe("withMarkerIds", () => {
  it("gives an id to every marker that arrives without one", () => {
    const result = withMarkerIds([
      { x: 1, y: 1, text: "a" },
      { x: 2, y: 2, text: "b" },
    ]);

    expect(result.every((m) => typeof m.id === "number")).toBe(true);
  });

  it("hands out ids that are unique within one call", () => {
    const markers: MarkerLike[] = Array.from({ length: 5 }, (_, i) => ({
      x: i,
      y: i,
      text: "point",
    }));

    const ids = withMarkerIds(markers).map((m) => m.id);

    expect(new Set(ids).size).toBe(markers.length);
  });

  it("does not hand out an id it already handed out in an earlier call", () => {
    const markers: MarkerLike[] = [
      { x: 1, y: 1, text: "a" },
      { x: 2, y: 2, text: "b" },
    ];

    const first = withMarkerIds(markers).map((m) => m.id);
    const second = withMarkerIds(markers).map((m) => m.id);

    expect(new Set([...first, ...second]).size).toBe(4);
  });

  it("keeps an id the marker already carries, including a falsy one", () => {
    // id 0 is what separates `??` from `||` here. The generator starts at 1, so 0 never comes
    // from us -- but an id that arrives as 0 must not be quietly replaced.
    const result = withMarkerIds([
      { x: 1, y: 1, text: "a", id: 42 },
      { x: 2, y: 2, text: "b" },
      { x: 3, y: 3, text: "c", id: 0 },
    ]);

    expect(must(result[2]).id).toBe(0);

    expect(must(result[0]).id).toBe(42);
    expect(must(result[1]).id).not.toBe(42);
  });

  it("carries every other field through untouched", () => {
    const result = withMarkerIds([{ x: 0.75, y: 0.25, text: "camp", color: "#abcdef" }]);

    expect(result[0]).toMatchObject({ x: 0.75, y: 0.25, text: "camp", color: "#abcdef" });
  });

  it("returns new objects and mutates neither the input array nor its markers", () => {
    const marker: MarkerLike = { x: 1, y: 2, text: "a" };
    const markers: MarkerLike[] = [marker];

    const result = withMarkerIds(markers);

    expect(result[0]).not.toBe(marker);
    expect(markers).toHaveLength(1);
    expect("id" in marker).toBe(false);
  });

  it("maps an empty list to an empty list", () => {
    expect(withMarkerIds([])).toEqual([]);
  });
});

describe("toRouteDoc", () => {
  it("stamps the frozen format and version", () => {
    const doc = toRouteDoc(draftOf(), FALLBACK_NAME);

    // Literals on purpose. Comparing the document with the module's own constants would stay
    // green if someone edited the constants, and every route file already on disk would stop
    // loading. The file format is the one thing here that is not ours to change.
    expect(doc.format).toBe("map-overlay-route");
    expect(doc.version).toBe(1);
    expect(ROUTE_FORMAT).toBe("map-overlay-route");
    expect(ROUTE_VERSION).toBe(1);
  });

  it("falls back to the default name when the name is empty or only whitespace", () => {
    expect(toRouteDoc(draftOf({ name: "" }), FALLBACK_NAME).name).toBe(FALLBACK_NAME);
    expect(toRouteDoc(draftOf({ name: "   \t\n " }), FALLBACK_NAME).name).toBe(FALLBACK_NAME);
  });

  it("trims a name that is not empty", () => {
    expect(toRouteDoc(draftOf({ name: "  Beluslan run  " }), FALLBACK_NAME).name).toBe(
      "Beluslan run",
    );
  });

  it("writes an empty map id when the draft has none", () => {
    expect(toRouteDoc(draftOf({ mapId: undefined }), FALLBACK_NAME).map).toBe("");
    expect(toRouteDoc(draftOf({ mapId: "" }), FALLBACK_NAME).map).toBe("");
  });

  it("copies the size, so editing the draft afterwards cannot reach the document", () => {
    const size: [number, number] = [2048, 1024];

    const doc = toRouteDoc(draftOf({ size }), FALLBACK_NAME);
    size[0] = 1;

    expect(doc.mapSize).toEqual([2048, 1024]);
    expect(doc.mapSize).not.toBe(size);
  });

  it("never writes an id, even when the draft markers carry one", () => {
    const doc = toRouteDoc(
      draftOf({
        markers: [
          { x: 1, y: 2, text: "a", id: 11 },
          { x: 3, y: 4, text: "b", color: "#00ff00", id: 12 },
        ],
      }),
      FALLBACK_NAME,
    );

    expect(doc.markers).toEqual([
      { x: 1, y: 2, text: "a" },
      { x: 3, y: 4, text: "b", color: "#00ff00" },
    ]);
    expect(doc.markers.map((m) => Object.keys(m))).toEqual([
      ["x", "y", "text"],
      ["x", "y", "text", "color"],
    ]);
  });

  it("keeps the style the draft carries", () => {
    expect(
      toRouteDoc(draftOf({ style: { color: "#010203", width: 7 } }), FALLBACK_NAME).style,
    ).toEqual({
      color: "#010203",
      width: 7,
    });
  });
});

describe("fromRouteDoc", () => {
  it("renames map to mapId and mapSize to size", () => {
    const draft = fromRouteDoc(storedDoc());

    expect(draft.mapId).toBe("beluslan");
    expect(draft.size).toEqual([8192, 8192]);
    expect(draft.name).toBe("Beluslan 40-45");
  });

  it("copies the size instead of aliasing the document", () => {
    const doc = storedDoc();

    const draft = fromRouteDoc(doc);
    doc.mapSize[0] = 1;

    expect(draft.size).toEqual([8192, 8192]);
  });

  it("gives every marker read from a file its own id", () => {
    const markers = fromRouteDoc(storedDoc()).markers;

    expect(markers).toHaveLength(3);
    expect(markers.every((m) => typeof m.id === "number")).toBe(true);
    expect(new Set(markers.map((m) => m.id)).size).toBe(3);
  });

  it("keeps the style a document carries", () => {
    const doc = storedDoc();
    doc.style = { color: "#010203", width: 7 };

    expect(fromRouteDoc(doc).style).toEqual({ color: "#010203", width: 7 });
  });

  it("falls back to the default style for a document saved without one", () => {
    const doc = docWithoutStyle();

    expect(fromRouteDoc(doc).style).toEqual(DEFAULT_ROUTE_STYLE);
    // The amber of the first palette entry. Pinned as a literal so a change is deliberate.
    expect(DEFAULT_ROUTE_STYLE).toEqual({ color: "#f2b544", width: 3 });
  });

  it("copies the default style rather than sharing the exported one", () => {
    const doc = docWithoutStyle();

    const style = fromRouteDoc(doc).style;
    style.width = 99;

    expect(DEFAULT_ROUTE_STYLE.width).toBe(3);
  });

  it("treats a document with no markers array as a route with no markers", () => {
    const doc = {
      format: ROUTE_FORMAT,
      version: ROUTE_VERSION,
      name: "Old route",
      map: "beluslan",
      mapSize: [8192, 8192],
      style: DEFAULT_ROUTE_STYLE,
    } as RouteDoc;

    expect(() => fromRouteDoc(doc)).not.toThrow();
    expect(fromRouteDoc(doc).markers).toEqual([]);
  });
});

describe("round trip", () => {
  it("returns a stored document unchanged through the editor shape", () => {
    const doc = storedDoc();

    expect(toRouteDoc(fromRouteDoc(doc), FALLBACK_NAME)).toEqual(storedDoc());
  });

  it("serialises identically after a round trip, which is what the dirty flag compares", () => {
    const doc = storedDoc();
    const before = JSON.stringify(doc);

    const after = JSON.stringify(toRouteDoc(fromRouteDoc(doc), FALLBACK_NAME));

    expect(after).toBe(before);
    expect(JSON.stringify(doc)).toBe(before);
  });
});

describe("markerWithIcon", () => {
  const base = { id: 1, x: 0, y: 0, text: "elder", color: "#6ea8ff" };

  it("brings a main quest's yellow and a side quest's green with the icon", () => {
    expect(markerWithIcon(base, "main")).toEqual({
      ...base,
      color: QUEST_COLOR.main,
      icon: "main",
    });
    expect(markerWithIcon(base, "side")).toEqual({
      ...base,
      color: QUEST_COLOR.side,
      icon: "side",
    });
  });

  it("keeps the colour when the icon is taken off", () => {
    const quest = markerWithIcon(base, "side");
    expect(markerWithIcon(quest, null)).toEqual({ ...base, color: QUEST_COLOR.side });
  });

  it("puts colour and icon last, in that order, as the file has them", () => {
    expect(Object.keys(markerWithIcon(base, "main"))).toEqual([
      "id",
      "x",
      "y",
      "text",
      "color",
      "icon",
    ]);
  });
});
