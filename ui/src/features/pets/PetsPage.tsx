import { useCallback, useMemo, useRef, useState } from "react";

import { useBackendState } from "@/shared/backend/BackendProvider";
import type { AppState } from "@/shared/backend/contract";
import { useSettingsPatch } from "@/shared/backend/useSettingsPatch";
import { useRemembered } from "@/shared/hooks/useRemembered";
import { type MessageKey, useT } from "@/shared/i18n";
import {
  levelOf,
  MAX_LEVEL,
  MAX_PICKED_PETS,
  type Pet,
  PET_COLORS,
  PET_MAPS,
  pickedOn,
  petsOf,
  SOULS,
  withLevel,
} from "@/shared/pets/pets";
import Icon, { type IconName } from "@/shared/ui/Icon";
import IconButton from "@/shared/ui/IconButton";
import Segmented from "@/shared/ui/Segmented";
import Sheen from "@/shared/ui/Sheen";

import PetRow from "./components/PetRow";
import PetsMap from "./components/PetsMap";
import "./pets.css";

type Show = "all" | "todo" | "done";
const SHOWS: readonly Show[] = ["all", "todo", "done"];
type View = "list" | "map";
const VIEWS: readonly { id: View; label: MessageKey; icon: IconName }[] = [
  { id: "list", label: "pets.tabs.list", icon: "list" },
  { id: "map", label: "pets.tabs.map", icon: "map" },
];
const ALL_SOULS = SOULS.reduce((a, b) => a + b, 0);

function matches(pet: Pet, query: string): boolean {
  if (!query) return true;
  const q = query.toLocaleLowerCase();
  return (
    pet.name.toLocaleLowerCase().includes(q) ||
    pet.monsters.some((m) => m.name.toLocaleLowerCase().includes(q))
  );
}

/**
 * The pets tool of the control panel: a map's pets as a checklist, each at the level the player
 * has it, and up to five of them picked to have their monsters' spots drawn over the game.
 *
 * The map is chosen here, as each faction's character hunts on its own: the active route's map
 * the first time, then whichever was chosen last.
 */
export default function PetsPage() {
  const t = useT();
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
  const [show, setShow] = useRemembered<Show>("mo.pets.show", SHOWS, "all");
  const [view, setView] = useRemembered<View>("mo.pets.view", ["list", "map"], "list");
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement | null>(null);

  const pets = petsOf(mapId);
  const levels = useMemo(() => settings?.pet_levels ?? {}, [settings?.pet_levels]);
  const picked = useMemo(() => settings?.pets ?? [], [settings?.pets]);
  const drawn = pickedOn(picked, mapId);
  const full = drawn.length >= MAX_PICKED_PETS;
  // keyed on the ids: `drawn` is a new array every render, and the map refits to what it shows
  const drawnKey = drawn.join(",");
  const shown = useMemo(
    () =>
      drawnKey
        .split(",")
        .filter(Boolean)
        .flatMap((id, i) => {
          const pet = pets.find((p) => p.id === id);
          return pet ? [{ pet, color: PET_COLORS[i] ?? "#ffffff" }] : [];
        }),
    [drawnKey, pets],
  );

  const onLevel = useCallback(
    (pet: Pet, level: number) => {
      changeSetting("pet_levels", withLevel(levels, mapId, pet.id, level));
      // A pet at the last level has nothing left to collect: its spots need no drawing.
      if (level >= MAX_LEVEL && picked.includes(pet.id)) {
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
      const next = on ? [...picked, pet.id] : picked.filter((id) => id !== pet.id);
      changeSetting("pets", next);
      if (on && !settings?.show_pets) changeSetting("show_pets", true);
    },
    [changeSetting, picked, settings?.show_pets],
  );

  if (!settings) return null;

  const level = (pet: Pet) => levelOf(levels, mapId, pet.id);
  const got = pets.filter((p) => level(p) > 0).length;
  const atTwo = pets.filter((p) => level(p) >= 2).length;
  const atThree = pets.filter((p) => level(p) >= MAX_LEVEL).length;
  const souls = pets.reduce(
    (sum, p) => sum + SOULS.slice(0, level(p)).reduce((a, b) => a + b, 0),
    0,
  );
  const share = pets.length ? souls / (pets.length * ALL_SOULS) : 0;

  const rows = pets.filter(
    (p) =>
      matches(p, query.trim()) &&
      (show === "all" || (show === "done" ? level(p) >= MAX_LEVEL : level(p) < MAX_LEVEL)),
  );
  const mapLabel = (id: string) => maps?.find((m) => m.id === id)?.label ?? id;
  const mapInfo = maps?.find((m) => m.id === mapId) ?? null;
  const mapView = mapInfo ? (
    <PetsMap map={mapInfo} shown={shown} />
  ) : (
    <p className="muted pe-map-note">{t("pets.mapPreparing")}</p>
  );
  const listView = (
    <div className="pe-list-view">
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
          <ul className="pe-list" aria-label={t("pets.list", { map: mapLabel(mapId) })}>
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

  return (
    <div className="pe-page">
      <section className="ui-frame pe-hero" aria-label={t("pets.label")}>
        <div className="pe-hero-main">
          <span className="pe-hero-mark" aria-hidden="true">
            <Icon name="paw" />
          </span>
          <span className="pe-hero-body">
            <span className="pe-hero-kicker">{mapLabel(mapId)}</span>
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
        <label className="pn-chip" title={t("pets.show")}>
          <input
            type="checkbox"
            checked={settings.show_pets}
            onChange={(e) => changeSetting("show_pets", e.target.checked)}
            aria-label={t("pets.show")}
          />
          <Icon name="paw" className="pn-chip-icon" />
          <span className="pn-chip-label" aria-hidden="true">
            {t("pets.showShort", { count: drawn.length, max: MAX_PICKED_PETS })}
          </span>
        </label>
        <ul className="pe-picked" aria-label={t("pets.picked")}>
          {drawn.length ? (
            drawn.map((id, i) => {
              const pet = pets.find((p) => p.id === id);
              return pet ? (
                <li key={id} style={{ "--pe-color": PET_COLORS[i] }}>
                  <span className="pe-dot" aria-hidden="true" />
                  {pet.name}
                </li>
              ) : null;
            })
          ) : (
            <li className="pe-picked-none">{t("pets.pickHint", { count: MAX_PICKED_PETS })}</li>
          )}
        </ul>
      </div>

      {PET_MAPS.length > 1 ? (
        <Segmented
          label={t("pets.map")}
          labelHidden
          value={mapId}
          options={PET_MAPS.map((id) => ({ value: id, label: mapLabel(id) }))}
          onChange={setMapId}
        />
      ) : null}

      <div role="tablist" aria-label={t("pets.label")} className="pn-menu pe-menu">
        {VIEWS.map(({ id, label, icon }) => {
          const on = id === view;
          return (
            <button
              key={id}
              id={`pe-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={on}
              aria-controls={`pe-view-${id}`}
              tabIndex={on ? 0 : -1}
              className={on ? "pn-tile on" : "pn-tile"}
              onClick={() => setView(id)}
              onKeyDown={(e) => {
                if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
                  e.preventDefault();
                  const next = id === "list" ? "map" : "list";
                  setView(next);
                  document.getElementById(`pe-tab-${next}`)?.focus();
                }
              }}
            >
              {on ? <Sheen /> : null}
              <Icon name={icon} className="pn-tile-icon" />
              <span className="pn-tile-label">{t(label)}</span>
            </button>
          );
        })}
      </div>

      <div id={`pe-view-${view}`} role="tabpanel" aria-labelledby={`pe-tab-${view}`}>
        {view === "map" ? mapView : listView}
      </div>
    </div>
  );
}
