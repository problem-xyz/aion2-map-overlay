"""Cut each pet's portrait out of the game's monster portraits, into one sheet for the app.

    uv run python scripts/import_pet_portraits.py \\
        --map altgard mapdata_altgard.json monsters_altgard.json mon_portraits_altgard.webp \\
        --map verteron mapdata_verteron.json monsters_verteron.json mon_portraits_verteron.webp

Each --map names a map's data extracted from the game client (the soul items and the monsters
they drop from, as scripts/import_pets.py reads it), its monster list and that list's portrait
atlas. The monster list reads:

    {"atlas": {"cell": 128, "cols": 16, ...},
     "species": {"2100144": {"n": "Smallbeak Airon", "por": 4, "pk": "exact", ...}, ...}}

`por` is the monster's cell in the atlas, left to right and top to bottom, and `pk` how the
portrait was matched to it: "exact" is the monster's own. Each atlas belongs to its own list --
the same model sits in different cells of two maps' atlases.

A pet's portrait is that of the first of its monsters whose portrait is its own, on the first
map given that has one; a pet with none keeps no portrait, and the app draws a paw for it. The
portraits are scaled to CELL pixels and written to assets/pets/portraits.webp, COLS to a row,
with assets/pets/portraits.json naming the pet in each cell:

    {"cell": 64, "cols": 16, "ids": ["534660031", ...]}
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "pets"

CELL = 64  # the side of a portrait in the sheet, in pixels
COLS = 16
QUALITY = 82


def pet_monsters(mapdata: dict[str, Any]) -> dict[str, list[int]]:
    """Each pet's soul item id and the monsters its souls drop from, in the order listed."""
    return {
        str(item_id): [int(n) for n in item["npc"]]
        for item_id, item in mapdata["items"].items()
        if str(item["n"]).startswith("Soul: ")
    }


def portrait_cell(monsters: list[int], species: dict[str, Any]) -> int | None:
    """The atlas cell of the first monster whose portrait is its own, or None."""
    for n in monsters:
        s = species.get(str(n))
        if s and s.get("pk") == "exact" and isinstance(s.get("por"), int):
            return int(s["por"])
    return None


def crop(atlas: Image.Image, cell: int, size: int, cols: int) -> Image.Image:
    col, row = cell % cols, cell // cols
    box = (col * size, row * size, col * size + size, row * size + size)
    return atlas.crop(box).resize((CELL, CELL), Image.Resampling.LANCZOS)


def sheet(portraits: list[Image.Image]) -> Image.Image:
    rows = max(1, -(-len(portraits) // COLS))
    out = Image.new("RGB", (COLS * CELL, rows * CELL), (16, 20, 27))
    for i, image in enumerate(portraits):
        out.paste(image, ((i % COLS) * CELL, (i // COLS) * CELL))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Cut the pets' portraits into one sheet.")
    parser.add_argument(
        "--map",
        nargs=4,
        action="append",
        required=True,
        metavar=("MAP", "MAPDATA", "MONSTERS", "ATLAS"),
        help="a map, its data, its monster list and that list's portrait atlas",
    )
    args = parser.parse_args()

    ids: list[str] = []
    portraits: list[Image.Image] = []
    for map_id, mapdata_path, monsters_path, atlas_path in args.map:
        pets = pet_monsters(json.loads(Path(mapdata_path).read_text(encoding="utf-8")))
        monsters = json.loads(Path(monsters_path).read_text(encoding="utf-8"))
        size, cols = int(monsters["atlas"]["cell"]), int(monsters["atlas"]["cols"])
        with Image.open(atlas_path) as raw:
            atlas = raw.convert("RGB")
        found = 0
        for pet_id, npcs in sorted(pets.items()):
            cell = None if pet_id in ids else portrait_cell(npcs, monsters["species"])
            if cell is None:
                continue
            ids.append(pet_id)
            portraits.append(crop(atlas, cell, size, cols))
            found += 1
        print(f"{map_id}: {found} portraits of {len(pets)} pets")

    OUT.mkdir(parents=True, exist_ok=True)
    sheet(portraits).save(OUT / "portraits.webp", "WEBP", quality=QUALITY, method=6)
    index = {"cell": CELL, "cols": COLS, "ids": ids}
    (OUT / "portraits.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"{len(ids)} portraits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
