import { useEffect } from "react";

import { useApi } from "@/shared/backend/hooks";
import { useT } from "@/shared/i18n";
import { PET_MAPS } from "@/shared/pets/pets";
import Segmented from "@/shared/ui/Segmented";

import PetsChecklist from "../components/PetsChecklist";
import PetsMap from "../components/PetsMap";
import PickedPets from "../components/PickedPets";
import { usePets } from "../hooks/usePets";
import "../pets.css";

/**
 * The pets' map, in a window of its own as large as the route editor's: the checklist down the
 * side, and the map beside it with the spots of the pets picked -- what the overlay will draw over
 * the game, to be looked at before going. Picks and levels are the panel's own: either window
 * changes them for both. Esc closes it, as it does the day timeline.
 */
export default function PetsMapPage() {
  const t = useT();
  const api = useApi();
  const p = usePets();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) api?.closePetsMap();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [api]);

  if (!p.settings) return null;

  return (
    <div className="pe-window">
      <aside className="pe-window-side" aria-label={t("pets.label")}>
        {PET_MAPS.length > 1 ? (
          <Segmented
            label={t("pets.map")}
            labelHidden
            value={p.mapId}
            options={PET_MAPS.map((id) => ({ value: id, label: p.mapLabel(id) }))}
            onChange={p.setMapId}
          />
        ) : null}
        <div className="pe-quick">
          <PickedPets
            shown={p.shown}
            on={p.settings.show_pets}
            onToggle={(on) => p.changeSetting("show_pets", on)}
          />
        </div>
        <PetsChecklist
          pets={p.pets}
          level={p.level}
          drawn={p.drawn}
          full={p.full}
          label={t("pets.list", { map: p.mapLabel(p.mapId) })}
          onLevel={p.onLevel}
          onPick={p.onPick}
        />
      </aside>
      <main className="pe-window-map">
        {p.mapInfo ? (
          <PetsMap map={p.mapInfo} shown={p.shown} />
        ) : (
          <p className="muted pe-map-note">{t("pets.mapPreparing")}</p>
        )}
      </main>
    </div>
  );
}
