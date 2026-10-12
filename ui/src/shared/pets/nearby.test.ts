import { describe, expect, it } from "vitest";

import { bestSpot, petsAtSpots } from "./nearby";
import { monstersOf, petsOf } from "./pets";

const ALTGARD = petsOf("altgard");
const byName = (name: string) => ALTGARD.find((p) => p.name === name)!;

describe("the pets at a pet's spots", () => {
  it("are listed for each of its spots, never the pet itself", () => {
    const armadon = byName("Armadon");
    const spots = petsAtSpots("altgard", armadon);

    expect(spots).toHaveLength(armadon.spots.length);
    expect(spots.flat().some((p) => p.id === armadon.id)).toBe(false);
  });
});

describe("a pet's best spot", () => {
  it("has the most of its monsters about one spot, a share of all it has", () => {
    const armadon = byName("Armadon");
    const best = bestSpot("altgard", armadon)!;

    expect(best.monsters).toBeGreaterThan(0);
    expect(best.monsters).toBeLessThanOrEqual(monstersOf(armadon));
    expect(best.spots).toBeGreaterThanOrEqual(1);
    for (const [x = 0, y = 0] of armadon.spots) {
      // no single spot alone holds more than the best place
      const alone = armadon.spots.find(([sx, sy]) => sx === x && sy === y)?.[2] ?? 0;
      expect(alone).toBeLessThanOrEqual(best.monsters);
    }
  });

  it("names the other pets in that one place, those with the most monsters first", () => {
    const best = bestSpot("altgard", byName("Armadon"))!;

    expect(best.others.length).toBeGreaterThan(0);
    for (let i = 1; i < best.others.length; i += 1) {
      expect(best.others[i - 1]!.monsters).toBeGreaterThanOrEqual(best.others[i]!.monsters);
    }
    expect(best.others.some((o) => o.pet.id === byName("Armadon").id)).toBe(false);
  });

  it("leaves out the pets not wanted, which no longer count toward the place", () => {
    const armadon = byName("Armadon");

    expect(bestSpot("altgard", armadon, () => false)!.others).toEqual([]);
  });

  it("is none for a pet with no spots", () => {
    expect(bestSpot("altgard", { ...byName("Armadon"), spots: [] })).toBeNull();
  });
});
