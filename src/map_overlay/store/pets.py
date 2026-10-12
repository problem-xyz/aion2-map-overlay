"""The pets: which there are on each map, and where the monsters that drop their souls stand.

assets/pets/<map>.json holds them (scripts/import_pets.py writes it), and the panel reads the
same files for its checklist. A pet is the id of its soul item, its name and genus, the monsters
its souls drop from, and its spots: [x, y, count], in percent of the map, each a camp of `count`
of those monsters. Its portrait, where the game has one, is a cell of assets/pets/portraits.webp,
which assets/pets/portraits.json names the pet of (scripts/import_pet_portraits.py).

What the player has of a pet is a level, 1 to 3, kept in settings.pet_levels under
"<map>:<pet id>" -- one faction's character never sees the other's map, so a pet's level on
Altgard says nothing of it on Verteron. Up to MAX_PICKED pets are drawn over the game at once,
picked by id in settings.pets; more, and the map is all marks.
"""

import functools
import json
import logging
import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import cv2
import numpy as np

from map_overlay.core.paths import resource_path

log = logging.getLogger(__name__)

# How many pets are drawn at once (MAX_PICKED_PETS in ui/src/features/pets/lib/pets.ts).
MAX_PICKED = 5
# The pet levels there are; a pet at the last has nothing left to collect.
MAX_LEVEL = 3


@functools.cache
def pets_of(map_id: str) -> list[dict[str, Any]]:
    """The map's pets, read once; none (and a log line) for a map without a usable file."""
    path = resource_path(f"assets/pets/{map_id}.json")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        log.warning("pets %s are not usable: %s", path, e)
        return []
    pets = doc.get("pets") if isinstance(doc, dict) else None
    if not isinstance(pets, list):
        log.warning("pets %s are not usable: no pets", path)
        return []
    return [p for p in pets if isinstance(p, dict) and isinstance(p.get("id"), str)]


def level_key(map_id: str, pet_id: str) -> str:
    """Where a pet's level is kept in settings.pet_levels."""
    return f"{map_id}:{pet_id}"


def pet_points(
    map_id: str, size: Sequence[float], picked: Iterable[str]
) -> dict[str, list[tuple[float, float]]]:
    """The spots of the pets picked that the map has, in map pixels of `size`, by pet id.

    In the order picked, no more than MAX_PICKED of them: the overlay gives each its own colour
    by that order, and the panel shows the same colour beside the pet.
    """
    w, h = float(size[0]), float(size[1])
    by_id = {p["id"]: p for p in pets_of(map_id)}
    out: dict[str, list[tuple[float, float]]] = {}
    for pid in picked:
        pet = by_id.get(pid)
        if pet is None or pid in out:
            continue
        out[pid] = [(s[0] / 100 * w, s[1] / 100 * h) for s in pet.get("spots") or []]
        if len(out) == MAX_PICKED:
            break
    return out


@functools.cache
def _portraits() -> tuple[np.ndarray | None, dict[str, int], int, int]:
    """The sheet of portraits as BGR pixels, each pet's cell, the cell's side and the columns."""
    index_path = resource_path("assets/pets/portraits.json")
    sheet_path = resource_path("assets/pets/portraits.webp")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        cell, cols = int(index["cell"]), int(index["cols"])
        ids = {str(pid): i for i, pid in enumerate(index["ids"])}
    except FileNotFoundError:
        return None, {}, 0, 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        log.warning("pet portraits %s are not usable: %s", index_path, e)
        return None, {}, 0, 0
    # imdecode, not imread: imread cannot open a path outside the ANSI code page on Windows
    data = np.fromfile(sheet_path, dtype=np.uint8) if sheet_path.exists() else None
    sheet = cv2.imdecode(data, cv2.IMREAD_COLOR) if data is not None and data.size else None
    if sheet is None:
        log.warning("pet portraits %s could not be read", sheet_path)
        return None, {}, 0, 0
    return sheet, ids, cell, cols


def portrait(pet_id: str) -> np.ndarray | None:
    """The pet's portrait as BGR pixels, square; None for a pet the game has none of."""
    sheet, ids, cell, cols = _portraits()
    at = ids.get(pet_id)
    if sheet is None or at is None:
        return None
    x, y = (at % cols) * cell, (at // cols) * cell
    found = sheet[y : y + cell, x : x + cell]
    return found if found.shape[:2] == (cell, cell) else None


# Where a pet is best farmed, as the panel's map works it out (ui/src/shared/pets/nearby.ts, which
# this mirrors): the spot with the most of its monsters within one round of farming, BEST_AREA world
# units about it; among the places with no fewer than BEST_OWN_SHARE of the most, the one where the
# monsters of the other pets still to collect add the most, each worth BEST_OTHERS_WEIGHT of one of
# its own. The world is 8160 units to its side; spots are in percent of it.
_UNIT = 100 / 8160
BEST_AREA = 80 * _UNIT
BEST_OWN_SHARE = 0.75
BEST_OTHERS_WEIGHT = 0.5


def best_spot(
    map_id: str, pet_id: str, levels: Mapping[str, int] | None = None
) -> tuple[float, float] | None:
    """The middle of a pet's best place, in percent of the map; None for a pet the map has not.

    `levels` is settings.pet_levels: a pet at the last level has nothing left to collect, and its
    monsters do not count toward another's place.
    """
    pets = pets_of(map_id)
    pet = next((p for p in pets if p["id"] == pet_id), None)
    if pet is None or not pet.get("spots"):
        return None
    levels = levels or {}
    wanted = {p["id"] for p in pets if levels.get(level_key(map_id, p["id"]), 0) < MAX_LEVEL} - {
        pet_id
    }
    near = [(float(x), float(y), int(n), p["id"]) for p in pets for x, y, n in p["spots"]]
    places: list[tuple[int, float, float, float]] = []  # own monsters, x, y, others' monsters
    for spot in pet["spots"]:
        x0, y0 = float(spot[0]), float(spot[1])
        own = others = 0
        sx = sy = 0.0
        for x, y, n, pid in near:
            if math.hypot(x - x0, y - y0) > BEST_AREA:
                continue
            if pid == pet_id:
                own += n
                sx += x * n
                sy += y * n
            elif pid in wanted:
                others += n
        places.append((own, sx / own, sy / own, others))
    most = max(own for own, *_ in places)
    best = max(
        (p for p in places if p[0] >= BEST_OWN_SHARE * most),
        key=lambda p: p[0] + BEST_OTHERS_WEIGHT * p[3],
    )
    return best[1], best[2]


def best_points(
    map_id: str, size: Sequence[float], pet_ids: Iterable[str], levels: Mapping[str, int]
) -> dict[str, tuple[float, float]]:
    """The best spot of each pet given that the map has, in map pixels of `size`, by pet id."""
    w, h = float(size[0]), float(size[1])
    out: dict[str, tuple[float, float]] = {}
    for pid in pet_ids:
        found = best_spot(map_id, pid, levels)
        if found is not None:
            out[pid] = (found[0] / 100 * w, found[1] / 100 * h)
    return out
