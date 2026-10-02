"""Object sets: points of interest drawn over a map in the editor.

A set belongs to its map and ships with it under assets/object-sets/. There is no importing
or removing one: the owner decided that a map's objects are fixed, as the maps themselves are.
Files a user imported before api 8 stay in maps/<id>/objects/ untouched and unread.
"""

import logging
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from map_overlay.core.errors import ObjectsError
from map_overlay.core.fileio import read_json_or_none
from map_overlay.store.resources import resource_of

log = logging.getLogger(__name__)


def validate_objects(doc: Any) -> dict[str, Any]:
    """Normalise an object set: categories, plus points in percent of the map size.

    Both the long spelling the sets in assets/object-sets use (categoryId/title/description)
    and the short form this app stores (c/t/d) are accepted, so a saved set still reads back.
    """
    if not isinstance(doc, dict):
        raise ObjectsError("objects.invalid.not_object")
    cats = {}
    for c in doc.get("categories") or []:
        if not isinstance(c, dict) or not c.get("id"):
            continue
        cats[str(c["id"])] = {
            "id": str(c["id"]),
            "name": str(c.get("name") or c["id"]),
            "parentId": str(c["parentId"]) if c.get("parentId") else None,
            "color": str(c.get("color") or "#8f99ad"),
        }
    nodes = []
    for n in doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        try:
            x, y = float(n["x"]), float(n["y"])
        except KeyError, TypeError, ValueError:
            continue
        cat = str(n.get("categoryId") or n.get("c") or "")
        if cat not in cats or not (0 <= x <= 100 and 0 <= y <= 100):
            continue
        nodes.append(
            {
                "c": cat,
                "x": round(x, 3),
                "y": round(y, 3),
                "t": str(n.get("title") or n.get("t") or ""),
                "d": str(n.get("description") or n.get("d") or ""),
            }
        )
    if not nodes:
        raise ObjectsError("objects.invalid.empty")
    return {
        "mapName": str(doc.get("mapName") or ""),
        "categories": list(cats.values()),
        "nodes": nodes,
    }


# How the UI names a set that ships with the app. Every set does since api 8: a map's objects
# come with the map and nothing else, so the prefix only keeps the names the UI already knows.
BUNDLED_PREFIX = "bundled/"


def load_bundled_set(path: Path, file: str) -> dict[str, Any] | None:
    """A bundled set in full, as the editor needs it; None (and a log line) if it does not load."""
    try:
        doc = validate_objects(read_json_or_none(path))
    except ObjectsError as e:
        log.warning("bundled object set %s is not usable: %s", path, e)
        return None
    doc["file"] = file
    doc["bundled"] = True
    return doc


# ------------------------------------------------------------------ the icon under a route point

# The maps of the Elyos, whose teleports the game marks with its blue winged figure.
ELYOS_MAPS = frozenset({"verteron"})

# How near an object a point is on it: within a map pixel, where the editor snaps a point.
ON_OBJECT = 1.0


def icon_for(category_id: str, map_name: str = "") -> str:
    """The icon the game draws for a category, or "" for a plain dot.

    The same rule as iconFor in ui/src/shared/ui/objectMarks.ts, which the editor and the panel
    draw by: the two have to agree, or the plaque would mark a point the lists leave plain.
    """
    if category_id.startswith("empyrean-trace"):
        return "trace"
    if category_id == "teleports":
        return "teleportElyos" if map_name.lower() in ELYOS_MAPS else "teleport"
    if category_id == "seals":
        return "seal"
    if category_id.startswith("hidden-cube"):
        return "cube"
    # a resource is drawn by its own mark, which bears the category's id (store/resources.py)
    if resource_of(category_id):
        return category_id
    return ""


def cube_points(sets: Iterable[dict[str, Any]], size: Sequence[float]) -> list[tuple[float, float]]:
    """Every hidden cube in the sets, in map pixels of `size`; the nodes are in percent of it."""
    w, h = float(size[0]), float(size[1])
    return [
        (n["x"] / 100 * w, n["y"] / 100 * h)
        for doc in sets
        for n in doc["nodes"]
        if icon_for(n["c"], doc.get("mapName", "")) == "cube"
    ]


def icons_under(
    sets: Iterable[dict[str, Any]],
    size: Sequence[float],
    points: Iterable[tuple[float, float]],
) -> list[str]:
    """The icon of the object under each point, in order; "" where there is none.

    Points are in map pixels, the sets' nodes in percent of `size`. Only objects that have an
    icon are looked at, a few thousand on a map, and they are filed by the whole pixel they fall
    in, so a point is checked against its own pixel and the eight around it.
    """
    w, h = float(size[0]), float(size[1])
    grid: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
    for doc in sets:
        icons = {c["id"]: icon_for(c["id"], doc.get("mapName", "")) for c in doc["categories"]}
        for n in doc["nodes"]:
            icon = icons.get(n["c"], "")
            if icon:
                x, y = n["x"] / 100 * w, n["y"] / 100 * h
                grid.setdefault((math.floor(x), math.floor(y)), []).append((x, y, icon))
    out = []
    for px, py in points:
        best, found = ON_OBJECT, ""
        cx, cy = math.floor(px), math.floor(py)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for x, y, icon in grid.get((gx, gy), ()):
                    d = math.hypot(x - px, y - py)
                    if d <= best:
                        best, found = d, icon
        out.append(found)
    return out
