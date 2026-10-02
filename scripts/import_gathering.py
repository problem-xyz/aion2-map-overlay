"""Bring the gathering points of aion2-interactive-map into the bundled object sets.

    uv run python scripts/import_gathering.py           # fetch and rewrite the two sets
    uv run python scripts/import_gathering.py --check   # fail if the sets are out of date

The upstream project's repository has no gathering markers; its site reads them from the data
it serves at data-aion2.tc-imba.com, the same project's data under the same licence (see NOTICE).
Each resource there is a subtype of the "gathering" category, gatheringOdyle and the like. Here
it becomes a child of a "gathering" category, with the id gathering-<name>, the name being the
resource's English name in the upstream locale, lower-cased: gathering-odyle.

Only the resources assets/marks/resources.json draws are taken; any other is reported and left
out, so a new resource upstream needs its drawing first. Everything else in a set is kept as it
is: the script removes the gathering categories and points it wrote last time and writes them
anew.

Positions are pixels on the 8192 x 8192 map layer from its top-left corner, as the site's other
markers; they become percentages of it, to three decimals.
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SETS = ROOT / "assets" / "object-sets"
MARKS = ROOT / "assets" / "marks" / "resources.json"

DATA = "https://data-aion2.tc-imba.com"
# Each bundled set and the upstream map it is adapted from.
MAPS = {"verteron": "World_L_A", "altgard": "World_D_A"}
LAYER = 8192  # the side of the upstream map layer, in pixels

PARENT = "gathering"
PREFIX = PARENT + "-"


def fetch(path: str) -> Any:
    request = urllib.request.Request(f"{DATA}/{path}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def resource_names(locale: dict[str, Any]) -> dict[str, str]:
    """Upstream subtype -> its English name, for the gathering subtypes."""
    return {
        key: str(entry.get("name") or key)
        for key, entry in (locale.get("subtypes") or {}).items()
        if key.startswith("gathering")
    }


def gathering(markers: list[dict[str, Any]], names: dict[str, str], drawn: list[str]):
    """The categories and nodes for one map: those of the resources `drawn` has, in its order."""
    by_id: dict[str, list[dict[str, Any]]] = {}
    skipped: dict[str, int] = {}
    for m in markers:
        if m.get("category") != "gathering":
            continue
        subtype = str(m.get("subtype") or "")
        name = names.get(subtype, subtype)
        rid = name.lower()
        if rid not in drawn:
            skipped[subtype] = skipped.get(subtype, 0) + 1
            continue
        by_id.setdefault(rid, []).append(
            {
                "id": f"oss-{m['id']}",
                "categoryId": PREFIX + rid,
                "x": round(float(m["x"]) / LAYER * 100, 3),
                "y": round(float(m["y"]) / LAYER * 100, 3),
                "title": name,
                "description": "",
            }
        )
    order = [rid for rid in drawn if rid in by_id]
    return order, by_id, skipped


def merged(doc: dict[str, Any], order, by_id, colors: dict[str, str]) -> dict[str, Any]:
    def ours(category_id: str) -> bool:
        return category_id == PARENT or category_id.startswith(PREFIX)

    categories = [c for c in doc["categories"] if not ours(str(c.get("id")))]
    nodes = [n for n in doc["nodes"] if not ours(str(n.get("categoryId")))]
    if order:
        categories.append({"id": PARENT, "name": "Gathering", "color": "#8f99ad"})
        for rid in order:
            categories.append(
                {
                    "id": PREFIX + rid,
                    "name": by_id[rid][0]["title"],
                    "parentId": PARENT,
                    "color": colors[rid],
                }
            )
            nodes.extend(sorted(by_id[rid], key=lambda n: n["id"]))
    return {**doc, "categories": categories, "nodes": nodes}


def text(doc: dict[str, Any]) -> str:
    return json.dumps(doc, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bring the gathering points into the object sets.")
    parser.add_argument("--check", action="store_true", help="compare, do not write")
    args = parser.parse_args()

    marks = json.loads(MARKS.read_text(encoding="utf-8"))
    drawn = [r["id"] for r in marks["resources"]]
    colors = {r["id"]: r["colors"]["main"] for r in marks["resources"]}
    names = resource_names(fetch("locales/en-US/types.json"))

    stale = []
    for set_name, upstream in MAPS.items():
        path = SETS / f"{set_name}.json"
        markers = fetch(f"markers/{upstream}.json")["markers"]
        order, by_id, skipped = gathering(markers, names, drawn)
        for subtype, count in sorted(skipped.items()):
            print(f"{set_name}: {subtype} ({count} points) has no drawing, left out")
        before = path.read_text(encoding="utf-8")
        after = text(merged(json.loads(before), order, by_id, colors))
        total = sum(len(v) for v in by_id.values())
        print(f"{set_name}: {total} gathering points in {len(order)} resources")
        if after == before:
            continue
        if args.check:
            stale.append(path.name)
        else:
            path.write_text(after, encoding="utf-8", newline="\n")
    if stale:
        print("out of date: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
