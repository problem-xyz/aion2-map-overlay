import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo } from "react";
import { MapContainer, Marker, TileLayer, Tooltip, useMap } from "react-leaflet";

import type { MapInfo } from "@/shared/backend/contract";
import { useT } from "@/shared/i18n";
import { mapBounds, pixelCRS, toLatLng } from "@/shared/map/crs";
import type { Pet } from "@/shared/pets/pets";
import { portraitStyle } from "@/shared/pets/portraits";

import type { ShownPet } from "../hooks/usePets";

/** A spot's mark, in CSS pixels: the portrait and the ring of the pet's colour round it. */
const SPOT_PX = 26;
const FACE_PX = 20;

export interface PetsMapProps {
  map: MapInfo;
  /** The pets picked that the map has, each in its colour: the ones the overlay draws. */
  shown: readonly ShownPet[];
}

/** One mark per pet: its portrait in a ring of its colour, or a dot of that colour. */
function spotIcon(pet: Pet, color: string): L.DivIcon {
  const face = portraitStyle(pet.id, FACE_PX);
  // built as an element and given as its markup: the browser quotes the sheet's address inside
  // the style attribute, and each marker gets a copy, where one element would move from marker to
  // marker and stay on the last
  const mark = document.createElement("span");
  mark.className = face ? "pe-spot-face" : "pe-spot-dot";
  if (face) Object.assign(mark.style, face);
  mark.style.setProperty("--pe-color", color);
  return L.divIcon({
    className: "pe-spot",
    html: mark.outerHTML,
    iconSize: [SPOT_PX, SPOT_PX],
    iconAnchor: [SPOT_PX / 2, SPOT_PX / 2],
  });
}

/**
 * Frames the spots shown, or the whole map with none; again whenever the pets change. The size is
 * measured again first: the tab the map is in may have been laid out after the map was made.
 */
function Frame({ points, whole }: { points: L.LatLng[]; whole: L.LatLngBounds }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    if (points.length) {
      map.fitBounds(L.latLngBounds(points), { padding: [24, 24], maxZoom: map.getMaxZoom() - 3 });
    } else {
      map.fitBounds(whole);
    }
  }, [map, points, whole]);
  return null;
}

/**
 * The map of the pets tool: the map the list is of, with the spots of the pets picked -- what the
 * overlay draws over the game, here to be looked at before going. A spot names its pet, its
 * monsters and how many of them stand there.
 */
export default function PetsMap({ map, shown }: PetsMapProps) {
  const t = useT();
  const { zMax, tile } = map.tiles;
  const zNative = map.tiles.zNative ?? zMax;
  const [width, height] = map.size;
  const crs = useMemo(() => pixelCRS(zMax), [zMax]);
  const bounds = useMemo(() => mapBounds([width, height]), [width, height]);

  const spots = useMemo(
    () =>
      shown.flatMap(({ pet, color }) => {
        const icon = spotIcon(pet, color);
        const monsters = [...new Set(pet.monsters.map((m) => m.name))].join(", ");
        return pet.spots.map(([x = 0, y = 0, count = 1], i) => ({
          key: `${pet.id}:${i}`,
          at: toLatLng((x / 100) * width, (y / 100) * height),
          icon,
          name: pet.name,
          monsters,
          count,
        }));
      }),
    [shown, width, height],
  );
  const points = useMemo(() => spots.map((s) => s.at), [spots]);

  if (!map.tiles.ready || !map.tilesUrl) {
    return <p className="muted pe-map-note">{t("pets.mapPreparing")}</p>;
  }
  const url = `${map.tilesUrl}/{z}/{x}/{y}.jpg`;

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
            </Tooltip>
          </Marker>
        ))}
        <Frame points={points} whole={bounds} />
      </MapContainer>
      {shown.length ? null : <p className="pe-map-hint">{t("pets.mapHint")}</p>}
    </div>
  );
}
