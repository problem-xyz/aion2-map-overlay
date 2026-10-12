import { type CSSProperties, memo } from "react";

import { type MessageKey, useT } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";

import { levelRange, MAX_PICKED_PETS, type Pet, SOULS } from "../lib/pets";
import { portraitStyle } from "../lib/portraits";

/** The portrait's side inside the switch's ring, in CSS pixels (.pe-pick in pets.css). */
const PORTRAIT_PX = 28;

export interface PetRowProps {
  pet: Pet;
  level: number;
  /** The colour it is drawn in over the game, while picked; null while it is not. */
  color: string | null;
  /** As many are picked as are drawn: one not picked cannot be. */
  full: boolean;
  onLevel: (pet: Pet, level: number) => void;
  onPick: (pet: Pet, on: boolean) => void;
}

/**
 * One pet in the checklist: its portrait, which is the switch that draws its monsters' spots over
 * the game, ringed in its colour while it does; its name, genus and monsters; and its three levels, each marked with the souls it
 * takes. A level clicked is reached, and every one before it; the level it is at, clicked again,
 * is taken back.
 */
function PetRow({ pet, level, color, full, onLevel, onPick }: PetRowProps) {
  const t = useT();
  const picked = color !== null;
  const face = portraitStyle(pet.id, PORTRAIT_PX);
  const style: CSSProperties | undefined = color ? { "--pe-color": color } : undefined;
  const pickLabel = picked
    ? t("pets.row.unpick", { name: pet.name })
    : full
      ? t("pets.row.full", { count: MAX_PICKED_PETS })
      : t("pets.row.pick", { name: pet.name });
  const monsters = pet.monsters.map((m) => m.name);
  const sub = [
    t(`pets.genus.${pet.genus}` as MessageKey),
    t("pets.row.levels", { range: levelRange(pet) }),
    [...new Set(monsters)].join(", "),
  ].join(" · ");

  return (
    <li
      className={`pe-row${picked ? " picked" : ""}${level >= SOULS.length ? " done" : ""}`}
      style={style}
    >
      <button
        type="button"
        className={`pe-pick${picked ? " on" : ""}${face ? " face" : ""}`}
        aria-pressed={picked}
        aria-label={pickLabel}
        title={pickLabel}
        disabled={full && !picked}
        onClick={() => onPick(pet, !picked)}
      >
        {face ? <span className="pe-face" style={face} /> : <Icon name="paw" />}
      </button>
      <span className="pe-row-text">
        <span className="pe-row-name">{pet.name}</span>
        <span className="pe-row-sub" title={sub}>
          {sub}
        </span>
      </span>
      <span className="pe-levels" role="group" aria-label={t("pets.row.levelLabel")}>
        {SOULS.map((souls, i) => {
          const n = i + 1;
          const reached = level >= n;
          return (
            <button
              key={n}
              type="button"
              className={reached ? "pe-level on" : "pe-level"}
              aria-pressed={reached}
              aria-label={t("pets.row.level", { level: n, souls })}
              title={t("pets.row.level", { level: n, souls })}
              onClick={() => onLevel(pet, level === n ? n - 1 : n)}
            >
              {souls}
            </button>
          );
        })}
      </span>
    </li>
  );
}

export default memo(PetRow);
