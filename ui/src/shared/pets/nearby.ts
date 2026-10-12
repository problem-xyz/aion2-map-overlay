/**
 * Which pets share their spots: monsters of several pets often stand in one camp, and the souls of
 * all of them drop there. Two spots are one place when they are within NEAR of each other: 50 world
 * units (metres), a little more than the 40 a spot gathers its monsters in (scripts/import_pets.py).
 *
 * Worked out once per map, the first time it is asked: a map has some two thousand spots, filed
 * by grid cell, each measured against the cells about it.
 */

import { type Pet, petsOf } from "./pets";

/** 50 world units in percent of the map: the world is 8160 units to its side. */
const NEAR = (50 / 8160) * 100;
/** The share of a pet's spots another must stand at to be farmed with it. */
const FARMED_SHARE = 0.25;

export interface NearbyPet {
  pet: Pet;
  /** How many of the first pet's spots this one stands at too. */
  shared: number;
}

interface MapNearby {
  /** pet id -> for each of its spots, the other pets standing there. */
  bySpot: Map<string, Pet[][]>;
}

const cache = new Map<string, MapNearby>();

function build(mapId: string): MapNearby {
  const pets = petsOf(mapId);
  const grid = new Map<string, { pet: Pet; x: number; y: number }[]>();
  const cell = (x: number, y: number) => `${Math.floor(x / NEAR)}:${Math.floor(y / NEAR)}`;
  for (const pet of pets) {
    for (const [x = 0, y = 0] of pet.spots) {
      const key = cell(x, y);
      let list = grid.get(key);
      if (!list) grid.set(key, (list = []));
      list.push({ pet, x, y });
    }
  }
  const bySpot = new Map<string, Pet[][]>();
  for (const pet of pets) {
    bySpot.set(
      pet.id,
      pet.spots.map(([x = 0, y = 0]) => {
        const here = new Map<string, Pet>();
        const cx = Math.floor(x / NEAR);
        const cy = Math.floor(y / NEAR);
        for (let dx = -1; dx <= 1; dx += 1) {
          for (let dy = -1; dy <= 1; dy += 1) {
            for (const other of grid.get(`${cx + dx}:${cy + dy}`) ?? []) {
              if (other.pet.id === pet.id || here.has(other.pet.id)) continue;
              if (Math.hypot(other.x - x, other.y - y) <= NEAR) here.set(other.pet.id, other.pet);
            }
          }
        }
        return [...here.values()];
      }),
    );
  }
  return { bySpot };
}

function nearbyOf(mapId: string): MapNearby {
  let found = cache.get(mapId);
  if (!found) cache.set(mapId, (found = build(mapId)));
  return found;
}

/** The other pets standing at each of a pet's spots, in the order of its spots. */
export function petsAtSpots(mapId: string, petId: string): readonly (readonly Pet[])[] {
  return nearbyOf(mapId).bySpot.get(petId) ?? [];
}

/**
 * The pets farmed with a pet: those standing at a good share of its spots -- a quarter of them, and
 * two at least -- those sharing the most first, no more than `most`, and only those `wanted`.
 * Nearly every pet stands by some other at a spot or two, which says nothing about where to farm
 * it.
 */
export function farmedWith(
  mapId: string,
  pet: Pet,
  wanted: (other: Pet) => boolean = () => true,
  most = 3,
): NearbyPet[] {
  const least = Math.max(2, Math.ceil(pet.spots.length * FARMED_SHARE));
  return nearbyPets(mapId, pet.id)
    .filter((n) => n.shared >= least && wanted(n.pet))
    .slice(0, most);
}

/** The pets that share a pet's spots, those sharing the most first. */
export function nearbyPets(mapId: string, petId: string): NearbyPet[] {
  const counts = new Map<string, NearbyPet>();
  for (const here of petsAtSpots(mapId, petId)) {
    for (const pet of here) {
      const entry = counts.get(pet.id);
      if (entry) entry.shared += 1;
      else counts.set(pet.id, { pet, shared: 1 });
    }
  }
  return [...counts.values()].sort(
    (a, b) => b.shared - a.shared || a.pet.name.localeCompare(b.pet.name),
  );
}
