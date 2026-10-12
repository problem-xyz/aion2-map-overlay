import { useCallback, useMemo } from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState } from "@/shared/backend/contract";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { useRemembered } from "@/shared/hooks/useRemembered";
import {
  levelOf,
  MAX_LEVEL,
  MAX_PICKED_PETS,
  type Pet,
  PET_COLORS,
  PET_MAPS,
  pickedOn,
  petsOf,
  withLevel,
} from "@/shared/pets/pets";

/** A pet the overlay draws, in the colour of its place among those picked. */
export interface ShownPet {
  pet: Pet;
  color: string;
}

/**
 * The pets of the map chosen, as the panel's tool and the map's window both show them: each at
 * its level, up to five picked to be drawn over the game, and what setting either changes.
 *
 * The map is chosen in either, as each faction's character hunts on its own: the active route's
 * map the first time, then whichever was chosen last.
 */
export function usePets() {
  const changeSetting = useSettingsPatch();
  const settings = useBackendState<AppState | null, AppState["settings"] | undefined>(
    (s) => s?.settings,
  );
  const maps = useBackendState<AppState | null, AppState["maps"] | undefined>((s) => s?.maps);
  const routeMap = useBackendState<AppState | null, string | undefined>(
    (s) => s?.routes.find((r) => r.id === s.route)?.map,
  );
  const [mapId, setMapId] = useRemembered<string>(
    "mo.pets.map",
    PET_MAPS,
    routeMap && PET_MAPS.includes(routeMap) ? routeMap : (PET_MAPS[0] ?? ""),
  );

  const pets = petsOf(mapId);
  const levels = useMemo(() => settings?.pet_levels ?? {}, [settings?.pet_levels]);
  const picked = useMemo(() => settings?.pets ?? [], [settings?.pets]);
  // keyed on the ids: pickedOn makes a new array every render, and the map refits to what it shows
  const drawnKey = pickedOn(picked, mapId).join(",");
  const drawn = useMemo(() => drawnKey.split(",").filter(Boolean), [drawnKey]);
  const shown = useMemo<ShownPet[]>(
    () =>
      drawn.flatMap((id, i) => {
        const pet = pets.find((p) => p.id === id);
        return pet ? [{ pet, color: PET_COLORS[i] ?? "#ffffff" }] : [];
      }),
    [drawn, pets],
  );

  const level = useCallback((pet: Pet) => levelOf(levels, mapId, pet.id), [levels, mapId]);
  const onLevel = useCallback(
    (pet: Pet, next: number) => {
      changeSetting("pet_levels", withLevel(levels, mapId, pet.id, next));
      // A pet at the last level has nothing left to collect: its spots need no drawing.
      if (next >= MAX_LEVEL && picked.includes(pet.id)) {
        changeSetting(
          "pets",
          picked.filter((id) => id !== pet.id),
        );
      }
    },
    [changeSetting, levels, mapId, picked],
  );
  const onPick = useCallback(
    (pet: Pet, on: boolean) => {
      changeSetting("pets", on ? [...picked, pet.id] : picked.filter((id) => id !== pet.id));
      if (on && !settings?.show_pets) changeSetting("show_pets", true);
    },
    [changeSetting, picked, settings?.show_pets],
  );

  const mapLabel = useCallback((id: string) => maps?.find((m) => m.id === id)?.label ?? id, [maps]);

  return {
    settings,
    changeSetting,
    mapId,
    setMapId,
    mapLabel,
    mapInfo: maps?.find((m) => m.id === mapId) ?? null,
    pets,
    level,
    drawn,
    shown,
    full: drawn.length >= MAX_PICKED_PETS,
    onLevel,
    onPick,
  };
}
