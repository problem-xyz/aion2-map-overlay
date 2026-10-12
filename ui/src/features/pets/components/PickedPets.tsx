import { useT } from "@/shared/i18n";
import { MAX_PICKED_PETS } from "@/shared/pets/pets";
import Icon from "@/shared/ui/Icon";

import type { ShownPet } from "../hooks/usePets";

export interface PickedPetsProps {
  shown: readonly ShownPet[];
  /** settings.show_pets: whether the overlay draws them. */
  on: boolean;
  onToggle: (on: boolean) => void;
}

/**
 * The switch that draws the pets picked over the game, and beside it which they are, each in its
 * colour; with none picked, how to pick them.
 */
export default function PickedPets({ shown, on, onToggle }: PickedPetsProps) {
  const t = useT();
  return (
    <>
      <label className="pn-chip" title={t("pets.show")}>
        <input
          type="checkbox"
          checked={on}
          onChange={(e) => onToggle(e.target.checked)}
          aria-label={t("pets.show")}
        />
        <Icon name="paw" className="pn-chip-icon" />
        <span className="pn-chip-label" aria-hidden="true">
          {t("pets.showShort", { count: shown.length, max: MAX_PICKED_PETS })}
        </span>
      </label>
      <ul className="pe-picked" aria-label={t("pets.picked")}>
        {shown.length ? (
          shown.map(({ pet, color }) => (
            <li key={pet.id} style={{ "--pe-color": color }}>
              <span className="pe-dot" aria-hidden="true" />
              {pet.name}
            </li>
          ))
        ) : (
          <li className="pe-picked-none">{t("pets.pickHint", { count: MAX_PICKED_PETS })}</li>
        )}
      </ul>
    </>
  );
}
