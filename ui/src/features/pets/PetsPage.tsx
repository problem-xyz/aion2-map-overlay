import { useApi } from "@/shared/backend/hooks";
import { useT } from "@/shared/i18n";
import { MAX_LEVEL, PET_MAPS, SOULS } from "@/shared/pets/pets";
import Icon from "@/shared/ui/Icon";
import Segmented from "@/shared/ui/Segmented";

import PetsChecklist from "./components/PetsChecklist";
import PickedPets from "./components/PickedPets";
import { usePets } from "./hooks/usePets";
import "./pets.css";

const ALL_SOULS = SOULS.reduce((a, b) => a + b, 0);

/**
 * The pets tool of the control panel: a map's pets as a checklist, each at the level the player
 * has it, and up to five of them picked to have their monsters' spots drawn over the game. Where
 * those spots are is seen before going in the map's own window, as large as the route editor.
 */
export default function PetsPage() {
  const t = useT();
  const api = useApi();
  const p = usePets();
  if (!p.settings || !api) return null;

  const { pets, level } = p;
  const got = pets.filter((pet) => level(pet) > 0).length;
  const atTwo = pets.filter((pet) => level(pet) >= 2).length;
  const atThree = pets.filter((pet) => level(pet) >= MAX_LEVEL).length;
  const souls = pets.reduce(
    (sum, pet) => sum + SOULS.slice(0, level(pet)).reduce((a, b) => a + b, 0),
    0,
  );
  const share = pets.length ? souls / (pets.length * ALL_SOULS) : 0;

  return (
    <div className="pe-page">
      <section className="ui-frame pe-hero" aria-label={t("pets.label")}>
        <div className="pe-hero-main">
          <span className="pe-hero-mark" aria-hidden="true">
            <Icon name="paw" />
          </span>
          <span className="pe-hero-body">
            <span className="pe-hero-kicker">{p.mapLabel(p.mapId)}</span>
            <span className="pe-hero-meta">
              {t("pets.hero.levels", { two: atTwo, three: atThree, total: pets.length })}
            </span>
          </span>
          <span className="pe-hero-count">
            <b>{got}</b>
            <span>/{pets.length}</span>
          </span>
        </div>
        <span
          className="pe-hero-prog"
          style={{ "--pe-p": share }}
          role="progressbar"
          aria-label={t("pets.hero.souls")}
          aria-valuemin={0}
          aria-valuemax={pets.length * ALL_SOULS}
          aria-valuenow={souls}
        />
      </section>

      <div className="pe-quick">
        <PickedPets
          shown={p.shown}
          on={p.settings.show_pets}
          onToggle={(on) => p.changeSetting("show_pets", on)}
          onRemove={(pet) => p.onPick(pet, false)}
        />
        <button type="button" className="pn-chip" onClick={() => api.openPetsMap()}>
          <Icon name="map" className="pn-chip-icon" />
          <span className="pn-chip-label">{t("pets.openMap")}</span>
        </button>
      </div>

      {PET_MAPS.length > 1 ? (
        <Segmented
          label={t("pets.map")}
          labelHidden
          value={p.mapId}
          options={PET_MAPS.map((id) => ({ value: id, label: p.mapLabel(id) }))}
          onChange={p.setMapId}
        />
      ) : null}

      <PetsChecklist
        mapId={p.mapId}
        mapLabel={p.mapLabel}
        bests={p.bests}
        pets={pets}
        level={level}
        drawn={p.drawn}
        full={p.full}
        label={t("pets.list", { map: p.mapLabel(p.mapId) })}
        onLevel={p.onLevel}
        onPick={p.onPick}
      />
    </div>
  );
}
