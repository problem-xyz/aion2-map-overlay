import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";

import type { MapInfo } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import { mapBounds, pixelCRS, toLatLng } from "@/shared/map/crs";
import { petsAtSpots } from "@/shared/pets/nearby";
import type { Pet } from "@/shared/pets/pets";
import { portraitStyle } from "@/shared/pets/portraits";
import Icon from "@/shared/ui/Icon";

import type { ShownPet } from "../hooks/usePets";

/** A spot's mark, in CSS pixels: the portrait and the ring of the pet's colour round it. */
const SPOT_PX = 26;
const FACE_PX = 20;
/** The best spot's mark: larger, with a star on its ring. */
const BEST_PX = 44;
const BEST_FACE_PX = 34;
/** A portrait in the card of best spots. */
const CARD_FACE_PX = 26;

export interface PetsMapProps {
  map: MapInfo;
  /** The pets picked that the map has, each in its colour: the ones the overlay draws. */
  shown: readonly ShownPet[];
}

/** One mark per pet: its portrait in a ring of its colour, or a dot of that colour. */
function spotIcon(pet: Pet, color: string, best = false): L.DivIcon {
  const size = best ? BEST_PX : SPOT_PX;
  const face = portraitStyle(pet.id, best ? BEST_FACE_PX : FACE_PX);
  // built as an element and given as its markup: the browser quotes the sheet's address inside
  // the style attribute, and each marker gets a copy, where one element would move from marker to
  // marker and stay on the last
  const mark = document.createElement("span");
  mark.className = face ? "pe-spot-face" : "pe-spot-dot";
  if (face) Object.assign(mark.style, face);
  mark.style.setProperty("--pe-color", color);
  let html = mark.outerHTML;
  if (best) {
    const star = document.createElement("span");
    star.className = "pe-best-star";
    star.textContent = "★";
    star.style.setProperty("--pe-color", color);
    html += star.outerHTML;
  }
  return L.divIcon({
    className: best ? "pe-spot pe-best" : "pe-spot",
    html,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** Hands the map out of its container, for the card beside it to fly it. */
function Grab({ onMap }: { onMap: (map: L.Map) => void }) {
  const map = useMap();
  useEffect(() => onMap(map), [map, onMap]);
  return null;
}

/**
 * Frames the spots shown, or the whole map with none: when the map opens and when the pets shown
 * change, not when a level is set. The size is measured again first: the window may have been laid
 * out after the map was made.
 */
function Frame({
  fitKey,
  points,
  whole,
}: {
  fitKey: string;
  points: L.LatLng[];
  whole: L.LatLngBounds;
}) {
  const map = useMap();
  const latest = useRef(points);
  latest.current = points;
  useEffect(() => {
    map.invalidateSize();
    const now = latest.current;
    if (now.length) {
      map.fitBounds(L.latLngBounds(now), { padding: [24, 24], maxZoom: map.getMaxZoom() - 3 });
    } else {
      map.fitBounds(whole);
    }
  }, [map, fitKey, whole]);
  return null;
}

/**
 * The map of the pets tool: the map the list is of, with the spots of the pets picked -- what the
 * overlay draws over the game, here to be looked at before going. A spot names its pet, its
 * monsters and how many of them stand there, and the other pets whose monsters stand there too.
 *
 * Each pet's best spot -- the most of its monsters within a round, the other pets still to collect
 * counted in -- wears a larger mark with a star, and the card in the corner flies to it.
 */
export default function PetsMap({ map, shown }: PetsMapProps) {
  const t = useT();
  const [leaflet, setLeaflet] = useState<L.Map | null>(null);
  const { zMax, tile } = map.tiles;
  const zNative = map.tiles.zNative ?? zMax;
  const [width, height] = map.size;
  const crs = useMemo(() => pixelCRS(zMax), [zMax]);
  const bounds = useMemo(() => mapBounds([width, height]), [width, height]);
  const at = (x: number, y: number) => toLatLng((x / 100) * width, (y / 100) * height);

  const spots = useMemo(
    () =>
      shown.flatMap(({ pet, color }) => {
        const icon = spotIcon(pet, color);
        const monsters = [...new Set(pet.monsters.map((m) => m.name))].join(", ");
        const others = petsAtSpots(map.id, pet);
        return pet.spots.map(([x = 0, y = 0, count = 1], i) => ({
          key: `${pet.id}:${i}`,
          at: toLatLng((x / 100) * width, (y / 100) * height),
          icon,
          name: pet.name,
          monsters,
          count,
          also: (others[i] ?? []).map((o) => o.name).join(", "),
        }));
      }),
    [shown, width, height, map.id],
  );
  const bests = useMemo(
    () =>
      shown.flatMap(({ pet, color, best }) =>
        best
          ? [
              {
                pet,
                color,
                best,
                at: toLatLng((best.x / 100) * width, (best.y / 100) * height),
                icon: spotIcon(pet, color, true),
              },
            ]
          : [],
      ),
    [shown, width, height],
  );
  const points = useMemo(() => spots.map((s) => s.at), [spots]);
  const fitKey = `${map.id}|${shown.map((s) => s.pet.id).join(",")}`;

  if (!map.tiles.ready || !map.tilesUrl) {
    return <p className="muted pe-map-note">{t("pets.mapPreparing")}</p>;
  }
  const url = `${map.tilesUrl}/{z}/{x}/{y}.jpg`;
  const others = (names: readonly { pet: Pet; monsters: number }[]) =>
    names
      .slice(0, 3)
      .map((o) => `${o.pet.name} ${o.monsters}`)
      .join(", ");

  return (
    <div className="pe-map">
      <MapContainer
        key={`${map.id}:${zMax}`}
        className="pe-map-canvas"
        crs={crs}
        bounds={bounds}
        maxBounds={bounds.pad(0.25)}
        maxBoundsViscosity={0.6}
        minZoom={Math.max(0, zMax - 5)}
        maxZoom={zMax + 2}
        zoomSnap={0.25}
        attributionControl={false}
      >
        <TileLayer
          key={`${url}:${zNative}`}
          url={url}
          tileSize={tile}
          maxNativeZoom={zNative}
          minNativeZoom={0}
          bounds={bounds}
          noWrap
        />
        {spots.map((s) => (
          <Marker key={s.key} position={s.at} icon={s.icon} keyboard={false}>
            <Tooltip direction="top" offset={[0, -SPOT_PX / 2]}>
              <b>{s.name}</b> · {s.count}
              <br />
              {s.monsters}
              {s.also ? (
                <>
                  <br />
                  <span className="pe-tip-also">{t("pets.mapAlso", { names: s.also })}</span>
                </>
              ) : null}
            </Tooltip>
          </Marker>
        ))}
        {bests.map((b) => (
          <Marker
            key={`best:${b.pet.id}`}
            position={b.at}
            icon={b.icon}
            keyboard={false}
            zIndexOffset={1000}
          >
            <Tooltip direction="top" offset={[0, -BEST_PX / 2]}>
              <b>★ {t("pets.best.of", { name: b.pet.name })}</b>
              <br />
              {t("pets.best.here", { monsters: b.best.monsters, spots: b.best.spots })}
              {b.best.others.length ? (
                <>
                  <br />
                  <span className="pe-tip-also">
                    {t("pets.mapAlso", { names: others(b.best.others) })}
                  </span>
                </>
              ) : null}
            </Tooltip>
          </Marker>
        ))}
        <Frame fitKey={fitKey} points={points} whole={bounds} />
        <Grab onMap={setLeaflet} />
      </MapContainer>

      {bests.length ? (
        <section className="pe-best-card" aria-label={t("pets.best.title")}>
          <h2 className="pe-best-title">{t("pets.best.title")}</h2>
          <ul>
            {bests.map((b) => {
              const face = portraitStyle(b.pet.id, CARD_FACE_PX);
              return (
                <li key={b.pet.id}>
                  <button
                    type="button"
                    className="pe-best-go"
                    style={{ "--pe-color": b.color }}
                    title={t("pets.best.go", { name: b.pet.name })}
                    onClick={() => leaflet?.flyTo(at(b.best.x, b.best.y), zMax, { duration: 0.6 })}
                  >
                    {face ? (
                      <span className="pe-best-face" style={face} />
                    ) : (
                      <Icon name="paw" className="pe-best-face" />
                    )}
                    <span className="pe-best-text">
                      <span className="pe-best-name">{b.pet.name}</span>
                      <span className="pe-best-meta">
                        ★ {t("pets.best.here", { monsters: b.best.monsters, spots: b.best.spots })}
                        {b.best.others.length ? ` · +${others(b.best.others)}` : ""}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
      {shown.length ? null : <p className="pe-map-hint">{t("pets.mapHint")}</p>}
    </div>
  );
}
