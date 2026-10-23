/**
 * The pets' portraits: one sheet, assets/pets/portraits.webp, and assets/pets/portraits.json naming
 * the pet in each cell (scripts/import_pet_portraits.py). The overlay draws its marks by the same
 * sheet (store/pets.py). A pet the game has no portrait of is in neither, and gets a paw.
 */

import type { CSSProperties } from "react";

import index from "../../../../assets/pets/portraits.json";
import sheet from "../../../../assets/pets/portraits.webp";

const CELLS: ReadonlyMap<string, number> = new Map(index.ids.map((id, i) => [id, i]));
const ROWS = Math.max(1, Math.ceil(index.ids.length / index.cols));

/** The background that shows the pet's portrait at `size` px; null for a pet with none. */
export function portraitStyle(petId: string, size: number): CSSProperties | null {
  const at = CELLS.get(petId);
  if (at === undefined) return null;
  const col = at % index.cols;
  const row = Math.floor(at / index.cols);
  return {
    backgroundImage: `url("${sheet}")`,
    backgroundSize: `${index.cols * size}px ${ROWS * size}px`,
    backgroundPosition: `-${col * size}px -${row * size}px`,
  };
}
