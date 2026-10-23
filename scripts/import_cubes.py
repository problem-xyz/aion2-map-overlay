"""Put a map's hidden cubes, every spot one can appear at, into its bundled object set.

    uv run python scripts/import_cubes.py cubes.json --map altgard
    uv run python scripts/import_cubes.py cubes.json --map altgard --check

The input is a list of the game's cube groups, each a name and the spots of that group in
world coordinates, [x, height, z]:

    [{"s": "EnvObj_D1_BasfeltRuins_HiddenBox_01_A", "pos": [[1292.3, 205.4, -1028.5], ...]}, ...]

The world lies on the 8192 x 8192 map layer centred, 8160 world units to its side, with no turn
and no flip: px = 4096 + x * 8192 / 8160, py = 4096 + z * 8192 / 8160. The 59 cubes the upstream
map shows on Altgard each sit on one spot of a group to a tenth of a pixel.

Each spot is told whether it is up or down: above or below the ground about it by more than
LEVEL_STEP. The ground is the median height of the upstream markers within NEAR pixels, the
gathering points and the places, whose heights the upstream data has; where fewer than MIN_NEAR
are near, it is the median of the spot's own group.

Each group is given a tint, an index into assets/marks/cubes.json, which the overlay and the
editor paint its cubes in: a cube is one of its group's spots, so its colour says which spots
are the same cube. Groups with spots within NEIGHBOURS pixels of each other get different tints.

The script replaces the nodes of the map's hidden-cube category and leaves the rest of the set
as it is.
"""

import argparse
import json
import re
import statistics
import sys
import urllib.request
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SETS = ROOT / "assets" / "object-sets"

DATA = "https://data-aion2.tc-imba.com"
# Each bundled set and the upstream map it is adapted from.
MAPS = {"verteron": "World_L_A", "altgard": "World_D_A"}
LAYER = 8192  # the side of the upstream map layer, in pixels
WORLD = 8160  # the side of the world it shows, in world units

NEAR = 100.0  # how far a marker is still about a spot, in layer pixels
MIN_NEAR = 3  # fewer markers near than this, and the spot's group is its ground
LEVEL_STEP = 20.0  # how much higher or lower than the ground a spot is up or down
NEIGHBOURS = 150.0  # groups with spots this close, in layer pixels, are tinted apart
TINTS = ROOT / "assets" / "marks" / "cubes.json"


def layer_px(x: float, z: float) -> tuple[float, float]:
    """A world position on the map layer, in pixels from its top-left corner."""
    k = LAYER / WORLD
    return LAYER / 2 + x * k, LAYER / 2 + z * k


def group_name(raw: str) -> str:
    """EnvObj_D1_BasfeltRuins_HiddenBox_01_A -> BasfeltRuins_01_A."""
    return re.sub(r"^EnvObj_[A-Z]\d+_", "", raw).replace("_HiddenBox", "")


def level(height: float, ground: float) -> str:
    """The spot's level: "up", "down", or "" where it is about as high as the ground."""
    if height - ground > LEVEL_STEP:
        return "up"
    if ground - height > LEVEL_STEP:
        return "down"
    return ""


def ground_at(px: float, py: float, markers: Sequence[tuple[float, float, float]]) -> float | None:
    """The median height of the markers near a point, or None if too few are."""
    near = [h for x, y, h in markers if (x - px) ** 2 + (y - py) ** 2 <= NEAR * NEAR]
    return statistics.median(near) if len(near) >= MIN_NEAR else None


def neighbours(groups: Sequence[Sequence[tuple[float, float]]]) -> list[set[int]]:
    """For each group, the groups with a spot within NEIGHBOURS of one of its own."""
    boxes = [
        (min(x for x, _ in g), min(y for _, y in g), max(x for x, _ in g), max(y for _, y in g))
        for g in groups
    ]
    near: list[set[int]] = [set() for _ in groups]
    for i, a in enumerate(groups):
        for j in range(i + 1, len(groups)):
            bi, bj = boxes[i], boxes[j]
            if (
                bj[0] - bi[2] > NEIGHBOURS
                or bi[0] - bj[2] > NEIGHBOURS
                or bj[1] - bi[3] > NEIGHBOURS
                or bi[1] - bj[3] > NEIGHBOURS
            ):
                continue
            close = any(
                (ax - bx) ** 2 + (ay - by) ** 2 <= NEIGHBOURS * NEIGHBOURS
                for ax, ay in a
                for bx, by in groups[j]
            )
            if close:
                near[i].add(j)
                near[j].add(i)
    return near


def tints(near: Sequence[set[int]], count: int) -> list[int]:
    """A tint for each group, none the same as a neighbour's where `count` tints allow it.

    The group whose neighbours already wear the most different tints goes next, ties to the one
    with more neighbours and then to the earlier one; it takes the first tint none of them wears,
    or failing that the one the fewest of them wear.
    """
    out: list[int | None] = [None] * len(near)
    for _ in near:
        i = max(
            (i for i, t in enumerate(out) if t is None),
            key=lambda i: (len({out[j] for j in near[i]} - {None}), len(near[i]), -i),
        )
        worn = [out[j] for j in near[i]]
        out[i] = min(range(count), key=lambda t: (worn.count(t), t))
    return [t for t in out if t is not None]


def group_tints(groups: Sequence[dict[str, Any]], count: int) -> tuple[list[int], int]:
    """Each group's tint, and how many pairs of neighbouring groups were left the same."""
    near = neighbours([[layer_px(float(p[0]), float(p[2])) for p in g["pos"]] for g in groups])
    out = tints(near, count)
    same = sum(1 for i, js in enumerate(near) for j in js if j > i and out[i] == out[j])
    return out, same


def cube_nodes(
    groups: Sequence[dict[str, Any]],
    markers: Sequence[tuple[float, float, float]],
    category: str,
    tint_of: Sequence[int],
) -> list[dict[str, Any]]:
    """The object-set nodes for every spot of every group, in the order the groups list them."""
    nodes = []
    for g, tint in zip(groups, tint_of, strict=True):
        name = group_name(str(g["s"]))
        spots = [(float(x), float(h), float(z)) for x, h, z in g["pos"]]
        own = statistics.median(h for _, h, _ in spots)
        for i, (x, h, z) in enumerate(spots, 1):
            px, py = layer_px(x, z)
            ground = ground_at(px, py, markers)
            node: dict[str, Any] = {
                "id": f"cube-{name}-{i:02d}",
                "categoryId": category,
                "x": round(px / LAYER * 100, 3),
                "y": round(py / LAYER * 100, 3),
                "title": "Hidden Cube",
                "description": "",
                "tint": tint,
            }
            lvl = level(h, own if ground is None else ground)
            if lvl:
                node["level"] = lvl
            nodes.append(node)
    return nodes


def merged(doc: dict[str, Any], category: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """The set with the category's nodes replaced by `nodes`, put where the old ones began."""
    old = doc["nodes"]
    at = next((i for i, n in enumerate(old) if n.get("categoryId") == category), len(old))
    kept = [n for n in old if n.get("categoryId") != category]
    return {**doc, "nodes": kept[:at] + nodes + kept[at:]}


def fetch(path: str) -> Any:
    request = urllib.request.Request(f"{DATA}/{path}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def ground_markers(markers: Iterable[dict[str, Any]]) -> list[tuple[float, float, float]]:
    """The upstream markers with a height, as (px, py, height); the cubes are not ground."""
    return [
        (float(m["x"]), float(m["y"]), float(m["z"]))
        for m in markers
        if m.get("subtype") != "hiddenCube" and m.get("z") is not None
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Put a map's hidden cubes into its object set.")
    parser.add_argument("cubes", type=Path, help="the cube groups, in world coordinates")
    parser.add_argument("--map", required=True, choices=sorted(MAPS))
    parser.add_argument("--check", action="store_true", help="compare, do not write")
    args = parser.parse_args()

    groups = json.loads(args.cubes.read_text(encoding="utf-8"))
    markers = ground_markers(fetch(f"markers/{MAPS[args.map]}.json")["markers"])
    category = f"hidden-cube-{args.map}"
    count = len(json.loads(TINTS.read_text(encoding="utf-8"))["tints"])
    tint_of, same = group_tints(groups, count)
    if same:
        print(f"{args.map}: {same} pairs of neighbouring groups share a tint", file=sys.stderr)
    nodes = cube_nodes(groups, markers, category, tint_of)

    path = SETS / f"{args.map}.json"
    before = path.read_text(encoding="utf-8")
    after = json.dumps(merged(json.loads(before), category, nodes), indent=2) + "\n"
    ups = sum(n.get("level") == "up" for n in nodes)
    downs = sum(n.get("level") == "down" for n in nodes)
    print(f"{args.map}: {len(nodes)} cubes in {len(groups)} groups, {ups} up, {downs} down")
    if after == before:
        return 0
    if args.check:
        print(f"out of date: {path.name}", file=sys.stderr)
        return 1
    path.write_text(after, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
