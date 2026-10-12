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
from collections.abc import Iterable, Sequence
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
