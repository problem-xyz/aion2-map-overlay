import { describe, expect, it } from "vitest";

import { farmedWith, nearbyPets, petsAtSpots } from "./nearby";
import { petsOf } from "./pets";

const ALTGARD = petsOf("altgard");
const byName = (name: string) => ALTGARD.find((p) => p.name === name)!;

describe("the pets at a pet's spots", () => {
  it("are listed for each of its spots, never the pet itself", () => {
    const armadon = byName("Armadon");
    const spots = petsAtSpots("altgard", armadon.id);

    expect(spots).toHaveLength(armadon.spots.length);
    expect(spots.flat().some((p) => p.id === armadon.id)).toBe(false);
  });

  it("count the spots they share, those sharing the most first", () => {
    const near = nearbyPets("altgard", byName("Armadon").id);

    expect(near[0]?.pet.name).toBe("Decomposed Lupyllini");
    for (let i = 1; i < near.length; i += 1) {
      expect(near[i - 1]!.shared).toBeGreaterThanOrEqual(near[i]!.shared);
    }
  });
});

describe("the pets farmed with a pet", () => {
  it("are those at a quarter of its spots or more, no more than three", () => {
    const armadon = byName("Armadon");
    const farmed = farmedWith("altgard", armadon);

    expect(farmed.map((n) => n.pet.name)).toEqual(["Decomposed Lupyllini"]);
    expect(farmed.every((n) => n.shared >= armadon.spots.length / 4)).toBe(true);
  });

  it("leave out the pets not wanted", () => {
    const armadon = byName("Armadon");

    expect(farmedWith("altgard", armadon, (p) => p.name !== "Decomposed Lupyllini")).toEqual([]);
  });
});
