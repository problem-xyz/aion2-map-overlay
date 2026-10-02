"""The gathering resources: which there are, in what order, and how each is drawn.

assets/marks/resources.json holds them, and the panel and the editor read the same file
(ui/src/shared/ui/markIcons.ts), so a resource looks the same over the game as in the lists.
Each resource is a shape -- a drawing on a 24px grid, as layers of SVG paths -- and the colours
it is painted in: a layer names its colours by role ("main", "ink") or gives one outright.

In an object set a resource is the category gathering-<id>, a child of "gathering"
(scripts/import_gathering.py writes them).
"""

import functools
import json
import logging
from collections.abc import Iterable, Sequence
from typing import Any

from map_overlay.core.paths import resource_path

log = logging.getLogger(__name__)

CATEGORY_PREFIX = "gathering-"


@functools.cache
def catalog() -> dict[str, Any]:
    """The file, read once; an empty catalog (and a log line) if it cannot be read."""
    path = resource_path("assets/marks/resources.json")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.warning("resource marks %s are not usable: %s", path, e)
        return {"shapes": {}, "resources": []}
    if not (
        isinstance(doc, dict)
        and isinstance(doc.get("shapes"), dict)
        and isinstance(doc.get("resources"), list)
    ):
        log.warning("resource marks %s are not usable: no shapes or resources", path)
        return {"shapes": {}, "resources": []}
    return doc


def resource_ids() -> list[str]:
    """Every resource, in the order the panel lists them."""
    return [str(r["id"]) for r in catalog()["resources"]]


def resource_of(category_id: str) -> str | None:
    """The resource an object set's category is, or None for any other category."""
    if not category_id.startswith(CATEGORY_PREFIX):
        return None
    rid = category_id[len(CATEGORY_PREFIX) :]
    return rid or None


def resources_in(sets: Iterable[dict[str, Any]]) -> list[str]:
    """The resources the sets have points of, in the catalog's order."""
    present = {rid for doc in sets for n in doc["nodes"] if (rid := resource_of(n["c"]))}
    return [rid for rid in resource_ids() if rid in present]


def resource_points(
    sets: Iterable[dict[str, Any]], size: Sequence[float]
) -> dict[str, list[tuple[float, float]]]:
    """Each resource's points in the sets, in map pixels of `size`; the nodes are in percent."""
    w, h = float(size[0]), float(size[1])
    out: dict[str, list[tuple[float, float]]] = {}
    for doc in sets:
        for n in doc["nodes"]:
            rid = resource_of(n["c"])
            if rid:
                out.setdefault(rid, []).append((n["x"] / 100 * w, n["y"] / 100 * h))
    return out


def resource_svg(rid: str) -> str | None:
    """The resource's drawing as an SVG document, 24 units square; None for one not drawn."""
    doc = catalog()
    res = next((r for r in doc["resources"] if r.get("id") == rid), None)
    layers = doc["shapes"].get(res.get("shape")) if res else None
    if not res or not layers:
        return None
    colors = res.get("colors") or {}
    paths = []
    for layer in layers:
        fill = layer.get("fill")
        stroke = layer.get("stroke")
        attrs = f'd="{layer["d"]}" fill="{colors.get(fill, fill) if fill else "none"}"'
        if stroke:
            width = layer.get("width", 1)
            attrs += f' stroke="{colors.get(stroke, stroke)}" stroke-width="{width}"'
        paths.append(f'<path {attrs} stroke-linecap="round" stroke-linejoin="round"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">' + "".join(paths) + "</svg>"
    )
