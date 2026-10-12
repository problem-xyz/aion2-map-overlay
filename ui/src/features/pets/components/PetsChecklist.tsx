import { useRef, useState } from "react";

import { useRemembered } from "@/shared/hooks/useRemembered";
import { type MessageKey, useT } from "@/shared/i18n";
import { farmedWith } from "@/shared/pets/nearby";
import { elsewhere, GENERA, type Genus, MAX_LEVEL, type Pet, PET_COLORS } from "@/shared/pets/pets";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";

import PetRow from "./PetRow";

type Show = "all" | "todo" | "done";
const SHOWS: readonly Show[] = ["all", "todo", "done"];
type GenusFilter = "all" | Genus;
const GENUS_FILTERS: readonly GenusFilter[] = ["all", ...GENERA];

function matches(pet: Pet, query: string): boolean {
  if (!query) return true;
  const q = query.toLocaleLowerCase();
  return (
    pet.name.toLocaleLowerCase().includes(q) ||
    pet.monsters.some((m) => m.name.toLocaleLowerCase().includes(q))
  );
}

export interface PetsChecklistProps {
  mapId: string;
  mapLabel: (mapId: string) => string;
  pets: readonly Pet[];
  level: (pet: Pet) => number;
  /** The pets drawn over the game, in the order that gives them their colours. */
  drawn: readonly string[];
  full: boolean;
  /** What the list is read out as: the pets of which map. */
  label: string;
  onLevel: (pet: Pet, level: number) => void;
  onPick: (pet: Pet, on: boolean) => void;
}

/**
 * A map's pets as a checklist: found by their name or a monster's, narrowed to a genus and to
 * those still to collect or those done, each row with its portrait to draw it over the game and
 * its levels. The list scrolls within itself, under the search and the filters, which stay.
 */
export default function PetsChecklist({
  mapId,
  mapLabel,
  pets,
  level,
  drawn,
  full,
  label,
  onLevel,
  onPick,
}: PetsChecklistProps) {
  const t = useT();
  const [show, setShow] = useRemembered<Show>("mo.pets.show", SHOWS, "all");
  const [genus, setGenus] = useRemembered<GenusFilter>("mo.pets.genus", GENUS_FILTERS, "all");
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement | null>(null);

  const rows = pets.filter(
    (p) =>
      matches(p, query.trim()) &&
      (genus === "all" || p.genus === genus) &&
      (show === "all" || (show === "done" ? level(p) >= MAX_LEVEL : level(p) < MAX_LEVEL)),
  );

  return (
    <div className="pe-checklist">
      <div className="pe-tools">
        <div className="pe-search">
          <label className="pe-search-field">
            <Icon name="search" />
            <span className="ui-sr-only">{t("pets.search")}</span>
            <input
              ref={searchRef}
              type="search"
              value={query}
              placeholder={t("pets.search")}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape" && query) {
                  // the search is cleared, and the map's window is not closed by the same key
                  e.preventDefault();
                  e.stopPropagation();
                  setQuery("");
                }
              }}
            />
          </label>
          {query ? (
            <IconButton
              className="pe-search-clear"
              icon={<Icon name="close" />}
              label={t("pets.clearSearch")}
              onClick={() => {
                setQuery("");
                searchRef.current?.focus();
              }}
            />
          ) : null}
        </div>
        <Segmented
          label={t("pets.filter.label")}
          labelHidden
          value={show}
          options={[
            { value: "all", label: t("pets.filter.all") },
            { value: "todo", label: t("pets.filter.todo") },
            { value: "done", label: t("pets.filter.done") },
          ]}
          onChange={setShow}
        />
      </div>

      <Segmented
        label={t("pets.genus.label")}
        labelHidden
        value={genus}
        options={GENUS_FILTERS.map((g) => ({
          value: g,
          label: t(g === "all" ? "pets.filter.all" : (`pets.genus.${g}` as MessageKey)),
        }))}
        onChange={setGenus}
      />

      <div className="ui-frame pe-list-card">
        {rows.length ? (
          <ul className="pe-list" aria-label={label}>
            {rows.map((pet) => {
              const at = drawn.indexOf(pet.id);
              // only a pet drawn names those farmed with it: the hint is about the trip it is on
              const nearby =
                at >= 0
                  ? farmedWith(mapId, pet, (other) => level(other) < MAX_LEVEL).map((n) => {
                      const theirs = drawn.indexOf(n.pet.id);
                      return { ...n, color: theirs >= 0 ? (PET_COLORS[theirs] ?? null) : null };
                    })
                  : undefined;
              const better = elsewhere(mapId, pet);
              return (
                <PetRow
                  key={pet.id}
                  pet={pet}
                  level={level(pet)}
                  color={at >= 0 ? (PET_COLORS[at] ?? null) : null}
                  full={full}
                  onLevel={onLevel}
                  onPick={onPick}
                  nearby={nearby}
                  elsewhere={better && { ...better, map: mapLabel(better.mapId) }}
                />
              );
            })}
          </ul>
        ) : (
          <p className="muted pe-none">{t("pets.none")}</p>
        )}
      </div>
    </div>
  );
}
