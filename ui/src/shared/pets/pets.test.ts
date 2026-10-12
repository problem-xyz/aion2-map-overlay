import { describe, expect, it } from "vitest";

import {
  levelOf,
  levelRange,
  MAX_PICKED_PETS,
  PET_MAPS,
  pickedOn,
  petsOf,
  withLevel,
} from "./pets";
import { portraitStyle } from "./portraits";

describe("the pets of each map", () => {
  it("are the shipped ones, 108 on Altgard and 113 on Verteron", () => {
    expect(PET_MAPS).toEqual(["altgard", "verteron"]);
    expect(petsOf("altgard")).toHaveLength(108);
    expect(petsOf("verteron")).toHaveLength(113);
    expect(petsOf("nowhere")).toEqual([]);
  });

  it("each carry a genus and the monsters their souls drop from", () => {
    for (const pet of petsOf("altgard")) {
      expect(["cogni", "fera", "natura", "varian"]).toContain(pet.genus);
      expect(pet.monsters.length).toBeGreaterThan(0);
    }
  });
});

describe("a pet's level", () => {
  it("is kept by map and pet, and 0 when not kept", () => {
    const levels = withLevel({}, "altgard", "1", 2);

    expect(levels).toEqual({ "altgard:1": 2 });
    expect(levelOf(levels, "altgard", "1")).toBe(2);
    expect(levelOf(levels, "verteron", "1")).toBe(0);
  });

  it("goes no higher than 3, and back to 0 is no entry at all", () => {
    expect(withLevel({}, "altgard", "1", 7)).toEqual({ "altgard:1": 3 });
    expect(withLevel({ "altgard:1": 2, "altgard:2": 1 }, "altgard", "1", 0)).toEqual({
      "altgard:2": 1,
    });
  });
});

describe("the pets picked", () => {
  it("are those the map has, in the order picked, no more than are drawn", () => {
    const ids = petsOf("verteron").map((p) => p.id);
    const picked = ["no-such-pet", ...ids.slice(0, MAX_PICKED_PETS + 1)];

    expect(pickedOn(picked, "verteron")).toEqual(ids.slice(0, MAX_PICKED_PETS));
  });
});

describe("the levels of a pet's monsters", () => {
  it("read as one level or the lowest to the highest", () => {
    const pet = { id: "1", name: "Airon", genus: "fera" as const, monsters: [], spots: [] };

    expect(levelRange({ ...pet, monsters: [{ name: "A", level: 18 }] })).toBe("18");
    expect(
      levelRange({
        ...pet,
        monsters: [
          { name: "A", level: 34 },
          { name: "B", level: 18 },
        ],
      }),
    ).toBe("18–34");
    expect(levelRange(pet)).toBe("");
  });
});

describe("a pet's portrait", () => {
  it("is its cell of the sheet at the size asked, and none for a pet without one", () => {
    const withFace = petsOf("altgard").find((p) => portraitStyle(p.id, 10));
    const style = withFace ? portraitStyle(withFace.id, 10) : null;

    expect(style?.backgroundImage).toMatch(/^url\(/);
    expect(style?.backgroundSize).toMatch(/^160px \d+0px$/); // 16 cells of 10 px to a row
    expect(portraitStyle("no-such-pet", 10)).toBeNull();
  });
});
