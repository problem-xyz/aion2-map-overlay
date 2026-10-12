/**
 * The pets of each map, out of assets/pets/<map>.json -- the files the overlay draws their spots
 * by too (store/pets.py). A pet is the id of its soul item, its name and genus as the game gives
 * them, the monsters its souls drop from, and its spots: [x, y, count] in percent of the map, each
 * a camp of `count` of those monsters.
 *
 * What the player has of a pet is a level, 1 to 3, in settings.pet_levels under "<map>:<id>";
 * a pet not named there is at 0. Up to MAX_PICKED_PETS of a map's pets are drawn over the game,
 * picked by id in settings.pets, each in the colour of its place among them.
 */

import altgard from "../../../../assets/pets/altgard.json";
import verteron from "../../../../assets/pets/verteron.json";

export type Genus = "cogni" | "fera" | "natura" | "varian";
export const GENERA: readonly Genus[] = ["cogni", "fera", "natura", "varian"];

export interface PetMonster {
  name: string;
  level: number;
}

export interface Pet {
  id: string;
  name: string;
  genus: Genus;
  monsters: readonly PetMonster[];
  spots: readonly (readonly number[])[];
}

/** How many of a map's pets are drawn at once (MAX_PICKED in store/pets.py). */
export const MAX_PICKED_PETS = 5;

/** Each picked pet's colour by its place among them, as the overlay paints its spots. */
export const PET_COLORS: readonly string[] = [
  "#f5c542",
  "#5cc8ff",
  "#ff7eb6",
  "#86e07a",
  "#b48cff",
];

/** The souls each level takes, from the one before it: 5 for the first, 25, then 75. */
export const SOULS: readonly number[] = [5, 25, 75];
export const MAX_LEVEL = SOULS.length;

interface PetsFile {
  pets: readonly {
    id: string;
    name: string;
    genus: string;
    monsters: readonly PetMonster[];
    spots: readonly (readonly number[])[];
  }[];
}

function read(file: PetsFile): Pet[] {
  return file.pets.map(({ id, name, genus, monsters, spots }) => ({
    id,
    name,
    genus: (GENERA as readonly string[]).includes(genus) ? (genus as Genus) : "fera",
    monsters,
    spots,
  }));
}

const BY_MAP: Readonly<Record<string, readonly Pet[]>> = {
  altgard: read(altgard),
  verteron: read(verteron),
};

/** The maps that have pets, in the order the panel offers them. */
export const PET_MAPS: readonly string[] = Object.keys(BY_MAP);

/** A map's pets, lowest level first; none for a map without them. */
export function petsOf(mapId: string): readonly Pet[] {
  return BY_MAP[mapId] ?? [];
}

export function levelKey(mapId: string, petId: string): string {
  return `${mapId}:${petId}`;
}

export function levelOf(levels: Readonly<Record<string, number>>, mapId: string, petId: string) {
  return levels[levelKey(mapId, petId)] ?? 0;
}

/** The levels with one pet's set: 0 drops it, as the file keeps no pet at 0. */
export function withLevel(
  levels: Readonly<Record<string, number>>,
  mapId: string,
  petId: string,
  level: number,
): Record<string, number> {
  const next = { ...levels };
  const key = levelKey(mapId, petId);
  if (level > 0) next[key] = Math.min(level, MAX_LEVEL);
  else delete next[key];
  return next;
}

/** The pets picked that the map has, in the order picked, no more than are drawn. */
export function pickedOn(picked: readonly string[], mapId: string): string[] {
  const ids = new Set(petsOf(mapId).map((p) => p.id));
  return picked.filter((id) => ids.has(id)).slice(0, MAX_PICKED_PETS);
}

/** The lowest and highest level of a pet's monsters, as "18" or "18–34". */
export function levelRange(pet: Pet): string {
  const levels = pet.monsters.map((m) => m.level);
  if (!levels.length) return "";
  const lo = Math.min(...levels);
  const hi = Math.max(...levels);
  return lo === hi ? String(lo) : `${lo}–${hi}`;
}
