import { type CSSProperties, memo } from "react";

import { type MessageKey, useT } from "@/shared/i18n";
import type { BestSpot, PetHere } from "@/shared/pets/nearby";
import { levelRange, MAX_PICKED_PETS, type Pet, SOULS } from "@/shared/pets/pets";
import { portraitStyle } from "@/shared/pets/portraits";
import Icon from "@/shared/ui/Icon";

/** The portrait's side inside the switch's ring, in CSS pixels (.pe-pick in pets.css). */
const PORTRAIT_PX = 28;
/** A pet farmed with it, as its row names it (.pe-near-face). */
const NEAR_PX = 18;

/** A pet farmed at its best spot, and its colour if it is drawn already. */
export interface RowNearby extends PetHere {
  color: string | null;
}

export interface PetRowProps {
  pet: Pet;
  level: number;
  /** The colour it is drawn in over the game, while picked; null while it is not. */
  color: string | null;
  /** As many are picked as are drawn: one not picked cannot be. */
  full: boolean;
  onLevel: (pet: Pet, level: number) => void;
  onPick: (pet: Pet, on: boolean) => void;
  /** Its best spot, and the pets farmed there with it, named under it while it is picked. */
  best?: BestSpot | null;
  nearby?: readonly RowNearby[];
  /** The other side, where its monsters are many more: the map's name and both counts. */
  elsewhere?: { map: string; here: number; there: number } | null;
}

/**
 * One pet in the checklist: its portrait, which is the switch that draws its monsters' spots over
 * the game, ringed in its colour while it does; its name, genus and monsters; and its three
 * levels, each marked with the souls it takes. A level clicked is reached, and every one before it;
 * the level it is at, clicked again, is taken back.
 *
 * While it is picked the row says how many of its monsters its best spot has, and names the other
 * pets farmed in that one place, each a click from being drawn as well: their souls drop on the
 * same round. A pet whose monsters are many more on the other
 * side says so, with both counts: there, through a rift, its souls come faster.
 */
function PetRow({
  pet,
  level,
  color,
  full,
  onLevel,
  onPick,
  best = null,
  nearby = [],
  elsewhere = null,
}: PetRowProps) {
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
        {elsewhere && level < SOULS.length ? (
          <span className="pe-elsewhere">
            <Icon name="map" className="pe-elsewhere-icon" />
            {t("pets.row.elsewhere", {
              map: elsewhere.map,
              there: elsewhere.there,
              here: elsewhere.here,
            })}
          </span>
        ) : null}
        {picked && best ? (
          <span className="pe-near">
            <span
              className="pe-near-best"
              title={t("pets.row.bestTip", { monsters: best.monsters, spots: best.spots })}
            >
              ★ {best.monsters}
            </span>
            {nearby.length ? <span className="pe-near-label">{t("pets.row.nearby")}</span> : null}
            {nearby.map((n) => {
              const nearFace = portraitStyle(n.pet.id, NEAR_PX);
              const tip = t("pets.row.nearbyTip", { name: n.pet.name, monsters: n.monsters });
              return (
                <button
                  key={n.pet.id}
                  type="button"
                  className={n.color ? "pe-near-pet on" : "pe-near-pet"}
                  style={n.color ? { "--pe-color": n.color } : undefined}
                  title={tip}
                  aria-label={n.color ? tip : t("pets.row.pick", { name: n.pet.name })}
                  disabled={Boolean(n.color) || full}
                  onClick={() => onPick(n.pet, true)}
                >
                  {nearFace ? (
                    <span className="pe-near-face" style={nearFace} />
                  ) : (
                    <Icon name="paw" className="pe-near-face" />
                  )}
                  <span className="pe-near-name">{n.pet.name}</span>
                  <span className="pe-near-count">{n.monsters}</span>
                </button>
              );
            })}
          </span>
        ) : null}
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
