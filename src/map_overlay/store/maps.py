"""The two maps the app ships with, and what it keeps for each of them on disk.

A map's reference image is a resource: assets/maps/<id>/reference.webp beside a manifest.json,
read-only and packaged with the app. The engine matches against it and routes are drawn in its
pixels. A map may also ship detail.webp, the same picture 2^k times larger, which only the
editor's tiles are cut from. Everything derived -- the thumbnail, the tile pyramid the editor
pans over, the object sets a user imports -- lives under userdata/maps/<id>/, created when
first written. Users neither add nor remove maps; the registry below is the whole list, in the
order the editor offers them.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from map_overlay.core.errors import MapError, ObjectsError
from map_overlay.core.fileio import read_json_or_none
from map_overlay.core.paths import DataDirs, resource_path
from map_overlay.store.images import data_url, image_size, imread, imwrite
from map_overlay.store.objects import BUNDLED_PREFIX, validate_objects
from map_overlay.store.resources import resources_in
from map_overlay.store.tiles import detail_octaves, tiles_info

log = logging.getLogger(__name__)

BUNDLED_MAP_IDS = ("altgard", "verteron")
FACTIONS = ("asmodian", "elyos")
MANIFEST = "manifest.json"
REFERENCE = "reference.webp"
DETAIL = "detail.webp"


@dataclass(frozen=True)
class BundledObjects:
    """An object set that ships with the app for one map: read-only, never imported or removed.

    `file` is what the UI knows it by. It carries a prefix no file under maps/<id>/objects/ can
    have, so a remove request for it matches nothing there.
    """

    file: str
    path: Path
    map_name: str
    nodes: int
    resources: tuple[str, ...] = ()  # the gathering resources it has points of, in list order


@dataclass(frozen=True)
class MapSpec:
    """One bundled map: what its manifest says, where its images are, and the sets it ships with.

    `detail` and `detail_size` are both set or both None.
    """

    id: str
    label: str
    size: tuple[int, int]
    reference: Path
    objects: tuple[BundledObjects, ...] = ()
    detail: Path | None = None
    detail_size: tuple[int, int] | None = None
    faction: str | None = None  # one of FACTIONS: whose zone the map is, for the route filter

    @property
    def tiles_source(self) -> Path:
        """The image the editor's tile pyramid is cut from."""
        return self.detail or self.reference


def bundled_maps_root() -> Path:
    """The folder holding one sub-folder per bundled map. Tests point this elsewhere."""
    return resource_path("assets/maps")


def bundled_objects_root() -> Path:
    """The folder holding <map id>.json for each map that ships with an object set."""
    return resource_path("assets/object-sets")


def load_bundled_maps(
    root: Path | None = None,
    ids: Sequence[str] = BUNDLED_MAP_IDS,
    objects_root: Path | None = None,
) -> tuple[MapSpec, ...]:
    """Every bundled map, in the registry's order.

    Raises MapError("map.manifest_invalid") on the first map whose manifest is missing, does
    not describe the image beside it, or has no image. That is a broken installation, and
    starting without maps would only move the failure to the first thing the user tries. A
    bundled object set that does not validate is only logged and left out: the map still works.

    The object sets are looked for beside the maps folder when a test passes its own `root`,
    so a test registry never picks up the real sets.
    """
    base = bundled_maps_root() if root is None else Path(root)
    if objects_root is None:
        objects_root = bundled_objects_root() if root is None else base.parent / "object-sets"
    return tuple(_load_spec(base / map_id, map_id, Path(objects_root)) for map_id in ids)


def _bundled_objects(objects_root: Path, map_id: str) -> tuple[BundledObjects, ...]:
    path = objects_root / f"{map_id}.json"
    if not path.is_file():
        return ()
    try:
        doc = validate_objects(read_json_or_none(path))
    except ObjectsError as e:
        log.warning("bundled object set %s is not usable, left out: %s", path, e)
        return ()
    name = doc["mapName"] or path.stem
    return (
        BundledObjects(
            BUNDLED_PREFIX + path.name,
            path,
            name,
            len(doc["nodes"]),
            tuple(resources_in([doc])),
        ),
    )


def _load_spec(folder: Path, map_id: str, objects_root: Path) -> MapSpec:
    def invalid(reason: str) -> MapError:
        return MapError("map.manifest_invalid", id=map_id, reason=reason)

    manifest = read_json_or_none(folder / MANIFEST)
    if not isinstance(manifest, dict):
        raise invalid(f"{folder / MANIFEST} is missing or is not a JSON object")
    if manifest.get("id") != map_id:
        raise invalid(f"the manifest says id {manifest.get('id')!r} in the folder {map_id!r}")
    label = manifest.get("label")
    if not isinstance(label, str) or not label.strip():
        raise invalid("the manifest has no label")
    size = _size_of(manifest, "size", invalid)
    reference = _image_of(folder / REFERENCE, size, invalid)
    faction = manifest.get("faction")
    if faction is not None and faction not in FACTIONS:
        raise invalid(f"the manifest's faction {faction!r} is not one of {FACTIONS}")
    detail = detail_size = None
    if "detail" in manifest:
        detail_size = _size_of(manifest, "detail", invalid)
        if not detail_octaves(size, detail_size):
            raise invalid("the manifest's detail is not the size doubled one or more times")
        detail = _image_of(folder / DETAIL, detail_size, invalid)
    return MapSpec(
        id=map_id,
        label=label.strip(),
        size=size,
        reference=reference,
        objects=_bundled_objects(objects_root, map_id),
        detail=detail,
        detail_size=detail_size,
        faction=faction,
    )


def _size_of(
    manifest: dict[str, Any], key: str, invalid: Callable[[str], MapError]
) -> tuple[int, int]:
    value = manifest.get(key)
    if not (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in value)
    ):
        raise invalid(f"the manifest's {key} is not two positive integers")
    return value[0], value[1]


def _image_of(path: Path, size: tuple[int, int], invalid: Callable[[str], MapError]) -> Path:
    if not path.is_file():
        raise invalid(f"{path} is missing")
    actual = image_size(path)
    if actual != size:
        raise invalid(
            f"the manifest says {size[0]}x{size[1]} for {path.name}, "
            f"the image is {actual[0]}x{actual[1]}"
        )
    return path


class ThumbCache:
    """Decoded map thumbnails and rendered route thumbnails, keyed by path and mtime.

    Owned by the caller rather than kept at module scope, so that tests and any second
    consumer never share one cache. Decoding a map thumbnail costs enough to be worth
    holding on to; one per map, since every state rebuild lists all of them.
    """

    def __init__(self, route_slots: int = 64) -> None:
        self._route_slots = route_slots
        self._maps = {}  # (path, mtime) -> ndarray
        self._backdrops = {}  # (path, mtime) -> ndarray
        self._routes = {}  # (path, mtime) -> data URL

    def backdrop(self, key: tuple[str, int], build: Callable[[], Any]) -> Any:
        """A map's backdrop, kept for every map: the route tiles of both maps are drawn in turn."""
        if key not in self._backdrops:
            self._backdrops = {k: v for k, v in self._backdrops.items() if k[0] != key[0]}
            self._backdrops[key] = build()
        return self._backdrops[key]

    def map_image(self, key: tuple[str, int], build: Callable[[], Any]) -> Any:
        # Kept per path: with a single slot, listing two maps evicted each in turn and every
        # state rebuild decoded both thumbnails from disk again.
        if key not in self._maps:
            self._maps = {k: v for k, v in self._maps.items() if k[0] != key[0]}
            self._maps[key] = build()
        return self._maps[key]

    def route_url(self, key: tuple[str, int], build: Callable[[], str]) -> str:
        if key in self._routes:
            return self._routes[key]
        result = build()
        if len(self._routes) > self._route_slots:
            self._routes.clear()
        self._routes[key] = result
        return result


def map_dir(dirs: DataDirs, map_id: str) -> Path:
    """Where the app keeps what it derives for a map. May not exist yet; writers create it."""
    return dirs.maps / map_id


def map_thumb(
    mdir: Path | str, reference: Path | str | None, cache: ThumbCache, width: int = 320
) -> Any:
    """Map thumbnail. The large reference is decoded once, thumb.jpg is read afterwards.

    Without a reference only an existing thumb.jpg is answered: the route thumbnails are drawn
    over the map's, after the map listing has cut it.
    """
    thumb_path = Path(mdir) / "thumb.jpg"
    if not thumb_path.exists():
        img = imread(reference, cv2.IMREAD_COLOR) if reference is not None else None
        if img is None:
            return None
        h = max(1, round(img.shape[0] * width / img.shape[1]))
        imwrite(
            thumb_path,
            cv2.resize(img, (width, h), interpolation=cv2.INTER_AREA),
            [cv2.IMWRITE_JPEG_QUALITY, 82],
        )
    key = (str(thumb_path), thumb_path.stat().st_mtime_ns)
    return cache.map_image(key, lambda: imread(thumb_path, cv2.IMREAD_COLOR))


# The image route tiles are cut from. Finer than the thumbnail, because a tile shows only the
# part of the map its route crosses, and much coarser than the reference, which takes a while
# to decode.
BACKDROP_WIDTH = 1536


def cut_backdrop(mdir: Path | str, reference: Path | str) -> None:
    """Write backdrop.jpg from the reference, unless it is there already."""
    path = Path(mdir) / "backdrop.jpg"
    if path.exists():
        return
    img = imread(reference, cv2.IMREAD_COLOR)
    if img is None:
        return
    h = max(1, round(img.shape[0] * BACKDROP_WIDTH / img.shape[1]))
    imwrite(
        path,
        cv2.resize(img, (BACKDROP_WIDTH, h), interpolation=cv2.INTER_AREA),
        [cv2.IMWRITE_JPEG_QUALITY, 85],
    )


def map_backdrop(mdir: Path | str, cache: ThumbCache) -> Any:
    """The decoded backdrop.jpg, or None while the map listing has not cut it."""
    path = Path(mdir) / "backdrop.jpg"
    try:
        key = (str(path), path.stat().st_mtime_ns)
    except OSError:
        return None
    return cache.backdrop(key, lambda: imread(path, cv2.IMREAD_COLOR))


def list_maps(dirs: DataDirs, specs: Sequence[MapSpec], cache: ThumbCache) -> list[dict[str, Any]]:
    """Every bundled map with its thumbnail, size and tile state, in registry order.

    Only the registry decides what is a map: a stray folder under userdata/maps/ is neither
    listed nor touched.
    """
    out = []
    for spec in specs:
        mdir = map_dir(dirs, spec.id)
        thumb = map_thumb(mdir, spec.reference, cache)
        cut_backdrop(mdir, spec.reference)
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "size": list(spec.size),
                "faction": spec.faction,
                "thumb": data_url(thumb) if thumb is not None else "",
                "tiles": tiles_info(mdir, spec.size, spec.detail_size),
                "objects": [
                    {"file": b.file, "mapName": b.map_name, "nodes": b.nodes, "bundled": True}
                    for b in spec.objects
                ],
                # what the panel's resource list offers on this map
                "resources": list(dict.fromkeys(r for b in spec.objects for r in b.resources)),
            }
        )
    return out
