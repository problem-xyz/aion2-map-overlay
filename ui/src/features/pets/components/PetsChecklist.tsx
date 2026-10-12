import { useRef, useState } from "react";

import { useRemembered } from "@/shared/hooks/useRemembered";
import { useT } from "@/shared/i18n";
import { MAX_LEVEL, type Pet, PET_COLORS } from "@/shared/pets/pets";
import Icon from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";

import PetRow from "./PetRow";

type Show = "all" | "todo" | "done";
const SHOWS: readonly Show[] = ["all", "todo", "done"];

function matches(pet: Pet, query: string): boolean {
  if (!query) return true;
  const q = query.toLocaleLowerCase();
  return (
    pet.name.toLocaleLowerCase().includes(q) ||
    pet.monsters.some((m) => m.name.toLocaleLowerCase().includes(q))
  );
}

export interface PetsChecklistProps {
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
 * A map's pets as a checklist: found by their name or a monster's, narrowed to those still to
 * collect or those done, each row with its portrait to draw it over the game and its levels.
 */
export default function PetsChecklist({
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
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement | null>(null);

  const rows = pets.filter(
    (p) =>
      matches(p, query.trim()) &&
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

      <div className="ui-frame pe-list-card">
        {rows.length ? (
          <ul className="pe-list" aria-label={label}>
            {rows.map((pet) => {
              const at = drawn.indexOf(pet.id);
              return (
                <PetRow
                  key={pet.id}
                  pet={pet}
                  level={level(pet)}
                  color={at >= 0 ? (PET_COLORS[at] ?? null) : null}
                  full={full}
                  onLevel={onLevel}
                  onPick={onPick}
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
