"""Write a map's pets, the monsters whose souls they are and where those monsters stand.

    uv run python scripts/import_pets.py mapdata_altgard.json --map altgard
    uv run python scripts/import_pets.py mapdata_altgard.json --map altgard --check

The input is a map's data as extracted from the game client, of which three keys are read:

    "items":    {"534660031": {"n": "Soul: Airon (Bound)", "npc": [2100144, ...]}, ...}
    "npcs":     {"2100144": {"n": "Smallbeak Airon", "lv": 18, "k": "Feral"}, ...}
    "monsters": [2100144, x, height, z, 2100144, x, height, z, ...]   (one spawn per four)

A pet is a soul item, "Soul: <pet> (Bound)": its souls drop from the monsters it lists, and the
pet's genus is theirs. Every spawn of those monsters is a place to get its souls; spawns within
SPOT_RADIUS world units of a spot's middle are one spot, so that a camp of twenty is one mark.

The world lies on the 8192 x 8192 map layer centred, 8160 world units to its side, with no turn
and no flip, as in scripts/import_cubes.py. A spot is written as percent of the layer, to three
decimals, with how many spawns it holds: [x, y, count].

The script writes assets/pets/<map>.json whole, a pet to a line.
"""

import argparse
import json
import math
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "pets"

MAPS = ("verteron", "altgard")
LAYER = 8192  # the side of the map layer, in pixels
WORLD = 8160  # the side of the world it shows, in world units

# How far a spawn may stand from the middle of a spot and still be of it, in world units
# (metres). Monsters of one camp stand within it; the next camp is past it.
SPOT_RADIUS = 40.0

# The game's genus of a monster, and the pet genus it is in the game's pet menu.
GENERA = {"Intellect": "cogni", "Feral": "fera", "Nature": "natura", "Trans": "varian"}

SOUL = re.compile(r"^Soul: (?P<name>.+?)(?: \(Bound\))?$")


def layer_percent(x: float, z: float) -> tuple[float, float]:
    """A world position as percent of the map layer, from its top-left corner."""
    k = LAYER / WORLD
    return (
        round((LAYER / 2 + x * k) / LAYER * 100, 3),
        round((LAYER / 2 + z * k) / LAYER * 100, 3),
    )


def pet_name(item_name: str) -> str | None:
    """ "Soul: Airon (Bound)" -> "Airon"; None for an item that is no pet's soul."""
    m = SOUL.match(item_name)
    return m.group("name") if m else None


def spawns_of(flat: Sequence[float]) -> list[tuple[int, float, float]]:
    """The flat spawn list as (monster, x, z); the height is not needed."""
    return [(int(flat[i]), float(flat[i + 1]), float(flat[i + 3])) for i in range(0, len(flat), 4)]


def spots(points: Iterable[tuple[float, float]]) -> list[tuple[float, float, int]]:
    """The points gathered into spots, as (x, z, count) in world units.

    Each point joins the first spot whose middle is within SPOT_RADIUS of it, and moves that
    middle; a point near none starts a spot. Order of the points decides close cases.
    """
    sums: list[list[float]] = []  # [sum x, sum z, count]
    for x, z in points:
        for s in sums:
            if math.dist((x, z), (s[0] / s[2], s[1] / s[2])) <= SPOT_RADIUS:
                s[0] += x
                s[1] += z
                s[2] += 1
                break
        else:
            sums.append([x, z, 1])
    return [(sx / n, sz / n, int(n)) for sx, sz, n in sums]


def pets(data: dict[str, Any]) -> list[dict[str, Any]]:
    """The map's pets, by the lowest level of their monsters, then by name."""
    npcs: dict[str, dict[str, Any]] = data["npcs"]
    by_monster: dict[int, list[tuple[float, float]]] = {}
    for monster, x, z in spawns_of(data["monsters"]):
        by_monster.setdefault(monster, []).append((x, z))

    out = []
    for item_id, item in data["items"].items():
        name = pet_name(str(item["n"]))
        if name is None:
            continue
        monsters = [npcs[str(n)] for n in item["npc"] if str(n) in npcs]
        genera = {GENERA.get(m["k"]) for m in monsters}
        if len(genera) != 1 or None in genera:
            raise ValueError(f"{name}: monsters of genera {sorted(map(str, genera))}")
        listed = sorted({(m["n"], int(m["lv"])) for m in monsters}, key=lambda m: (m[1], m[0]))
        points = [p for n in item["npc"] for p in by_monster.get(int(n), [])]
        out.append(
            {
                "id": str(item_id),
                "name": name,
                "genus": genera.pop(),
                "monsters": [{"name": n, "level": lv} for n, lv in listed],
                "spots": [[*layer_percent(x, z), n] for x, z, n in spots(points)],
            }
        )
    return sorted(out, key=lambda p: (p["monsters"][0]["level"] if p["monsters"] else 0, p["name"]))


def document(map_id: str, data: dict[str, Any]) -> dict[str, Any]:
    client = data.get("client", {}).get("label", "the game client")
    return {
        "map": map_id,
        "source": f"{client}: the soul items, the monsters they drop from and their spawns",
        "pets": pets(data),
    }


def dumped(doc: dict[str, Any]) -> str:
    """The document as JSON with each pet on a line of its own, so a diff names the pets."""
    head = {k: v for k, v in doc.items() if k != "pets"}
    lines = [json.dumps(p, ensure_ascii=False, separators=(",", ":")) for p in doc["pets"]]
    top = json.dumps(head, ensure_ascii=False, indent=2)[:-2]
    return top + ',\n  "pets": [\n    ' + ",\n    ".join(lines) + "\n  ]\n}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a map's pets and their monsters' spots.")
    parser.add_argument("mapdata", type=Path, help="the map's data extracted from the game")
    parser.add_argument("--map", required=True, choices=MAPS)
    parser.add_argument("--check", action="store_true", help="compare, do not write")
    args = parser.parse_args()

    doc = document(args.map, json.loads(args.mapdata.read_text(encoding="utf-8")))
    path = OUT / f"{args.map}.json"
    after = dumped(doc)
    before = path.read_text(encoding="utf-8") if path.exists() else ""
    spot_count = sum(len(p["spots"]) for p in doc["pets"])
    print(f"{args.map}: {len(doc['pets'])} pets, {spot_count} spots")
    if after == before:
        return 0
    if args.check:
        print(f"out of date: {path.name}", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(after, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
