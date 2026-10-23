import { useT } from "@/shared/i18n";
import { MAX_PICKED_PETS, type Pet } from "@/shared/pets/pets";
import { portraitStyle } from "@/shared/pets/portraits";
import Icon from "@/shared/ui/Icon";

import type { ShownPet } from "../hooks/usePets";

/** A slot's portrait, in CSS pixels (.pe-slot-face in pets.css). */
const FACE_PX = 30;

export interface PickedPetsProps {
  shown: readonly ShownPet[];
  /** settings.show_pets: whether the overlay draws them. */
  on: boolean;
  onToggle: (on: boolean) => void;
  onRemove: (pet: Pet) => void;
}

/**
 * The switch that draws the pets picked over the game, and the five places they take: each
 * picked pet's portrait in its colour, which takes it off the map when clicked, and an empty ring
 * for each place still free. With the switch off the places are dimmed, as nothing is drawn.
 */
export default function PickedPets({ shown, on, onToggle, onRemove }: PickedPetsProps) {
  const t = useT();
  const free = Math.max(0, MAX_PICKED_PETS - shown.length);
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
          {t("pets.showShort")}
        </span>
      </label>
      <ul
        className={on ? "pe-slots" : "pe-slots off"}
        aria-label={t("pets.picked", { count: shown.length, max: MAX_PICKED_PETS })}
        title={shown.length ? undefined : t("pets.pickHint", { count: MAX_PICKED_PETS })}
      >
        {shown.map(({ pet, color }) => {
          const face = portraitStyle(pet.id, FACE_PX);
          const label = t("pets.row.unpick", { name: pet.name });
          return (
            <li key={pet.id}>
              <button
                type="button"
                className="pe-slot"
                style={{ "--pe-color": color }}
                aria-label={label}
                title={pet.name}
                onClick={() => onRemove(pet)}
              >
                {face ? (
                  <span className="pe-slot-face" style={face} />
                ) : (
                  <Icon name="paw" className="pe-slot-paw" />
                )}
                <span className="pe-slot-x" aria-hidden="true">
                  <Icon name="close" />
                </span>
              </button>
            </li>
          );
        })}
        {Array.from({ length: free }, (_, i) => (
          <li key={`free-${i}`} className="pe-slot-free" aria-hidden="true" />
        ))}
      </ul>
    </>
  );
}
