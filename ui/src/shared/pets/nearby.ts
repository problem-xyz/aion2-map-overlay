/**
 * Where a pet is best farmed, and who else is farmed there.
 *
 * A pet's best place is the spot with the most of its monsters about it, within AREA: a camp and
 * the camps a few steps from it, which are cleared on one round. Between places with nearly as
 * many, the monsters of other pets standing there decide: their souls drop on the same round.
 * Two spots are one place, for the map's tooltips, when they are within NEAR: a little more than
 * the 40 world units a spot gathers its monsters in (scripts/import_pets.py).
 *
 * Every map's spots are filed by grid cell the first time it is asked, each then measured against
 * the cells about it: a map has some two thousand spots. The overlay works the best spot out the
 * same way, in store/pets.py best_spot: a change to the one is a change to the other.
 */

import { type Pet, petsOf } from "./pets";

/** World units in percent of the map: the world is 8160 units to its side. */
const UNIT = 100 / 8160;
/** One place, for the tooltips: 50 world units. */
const NEAR = 50 * UNIT;
/** One round of farming: 80 world units about a spot. */
const AREA = 80 * UNIT;
/** What another pet's monster in the same place is worth beside one of the pet's own. */
const OTHERS_WEIGHT = 0.5;
/** A place is a candidate with at least this share of the most of the pet's own any place has. */
const OWN_SHARE = 0.75;

interface Placed {
  pet: Pet;
  x: number;
  y: number;
  count: number;
}

const grids = new Map<string, Map<string, Placed[]>>();

function cellOf(x: number, y: number): [number, number] {
  return [Math.floor(x / AREA), Math.floor(y / AREA)];
}

function gridOf(mapId: string): Map<string, Placed[]> {
  let grid = grids.get(mapId);
  if (grid) return grid;
  grid = new Map();
  for (const pet of petsOf(mapId)) {
    for (const [x = 0, y = 0, count = 1] of pet.spots) {
      const [cx, cy] = cellOf(x, y);
      const key = `${cx}:${cy}`;
      let list = grid.get(key);
      if (!list) grid.set(key, (list = []));
      list.push({ pet, x, y, count });
    }
  }
  grids.set(mapId, grid);
  return grid;
}

/** Every spot of every pet within `radius` of (x, y); the radius is no more than AREA. */
function around(mapId: string, x: number, y: number, radius: number): Placed[] {
  const grid = gridOf(mapId);
  const [cx, cy] = cellOf(x, y);
  const found: Placed[] = [];
  for (let dx = -1; dx <= 1; dx += 1) {
    for (let dy = -1; dy <= 1; dy += 1) {
      for (const p of grid.get(`${cx + dx}:${cy + dy}`) ?? []) {
        if (Math.hypot(p.x - x, p.y - y) <= radius) found.push(p);
      }
    }
  }
  return found;
}

/** The other pets standing at each of a pet's spots, in the order of its spots. */
export function petsAtSpots(mapId: string, pet: Pet): readonly (readonly Pet[])[] {
  return pet.spots.map(([x = 0, y = 0]) => {
    const here = new Map<string, Pet>();
    for (const p of around(mapId, x, y, NEAR)) if (p.pet.id !== pet.id) here.set(p.pet.id, p.pet);
    return [...here.values()];
  });
}

/** Another pet farmed in the same place, and how many of its monsters stand there. */
export interface PetHere {
  pet: Pet;
  monsters: number;
}

export interface BestSpot {
  /** The middle of the pet's monsters there, in percent of the map. */
  x: number;
  y: number;
  /** How many of the pet's monsters stand there, and in how many of its spots. */
  monsters: number;
  spots: number;
  /** The other pets farmed there, those with the most monsters first. */
  others: PetHere[];
}

/**
 * Where a pet is best farmed: among the places with nearly the most of its own monsters -- no
 * fewer than OWN_SHARE of the most any place has -- the one where the monsters of the other pets
 * `wanted` add the most. Its own monsters come first: a place full of others' and few of its own
 * is not where it is farmed. Null for a pet with no spots.
 */
export function bestSpot(
  mapId: string,
  pet: Pet,
  wanted: (other: Pet) => boolean = () => true,
): BestSpot | null {
  const places: BestSpot[] = [];
  for (const [x = 0, y = 0] of pet.spots) {
    let monsters = 0;
    let spots = 0;
    let sx = 0;
    let sy = 0;
    const others = new Map<string, PetHere>();
    for (const p of around(mapId, x, y, AREA)) {
      if (p.pet.id === pet.id) {
        monsters += p.count;
        spots += 1;
        sx += p.x * p.count;
        sy += p.y * p.count;
      } else if (wanted(p.pet)) {
        const entry = others.get(p.pet.id);
        if (entry) entry.monsters += p.count;
        else others.set(p.pet.id, { pet: p.pet, monsters: p.count });
      }
    }
    places.push({
      x: sx / monsters,
      y: sy / monsters,
      monsters,
      spots,
      others: [...others.values()].sort(
        (a, b) => b.monsters - a.monsters || a.pet.name.localeCompare(b.pet.name),
      ),
    });
  }
  const most = Math.max(0, ...places.map((place) => place.monsters));
  const score = (place: BestSpot) =>
    place.monsters + OTHERS_WEIGHT * place.others.reduce((sum, o) => sum + o.monsters, 0);
  let best: BestSpot | null = null;
  for (const place of places) {
    if (place.monsters < OWN_SHARE * most) continue;
    if (!best || score(place) > score(best)) best = place;
  }
  return best;
}
