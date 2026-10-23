"""scripts/import_pets.py: a map's soul items, their monsters and spawns, into its pets file."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ip = load_script(REPO / "scripts" / "import_pets.py", "import_pets")


def test_the_world_centre_is_the_middle_of_the_layer() -> None:
    assert ip.layer_percent(0, 0) == (50, 50)


def test_the_world_edge_is_the_layer_edge() -> None:
    assert ip.layer_percent(-4080, 4080) == pytest.approx((0, 100))


@pytest.mark.parametrize(
    ("item", "name"),
    [
        ("Soul: Airon (Bound)", "Airon"),
        ("Soul: Drakan Guard Dog", "Drakan Guard Dog"),
        ("Artwork: Soul Ruler Kashapa", None),
        ("Wisdom Greatsword", None),
    ],
)
def test_a_pet_is_named_by_its_soul(item: str, name: str | None) -> None:
    assert ip.pet_name(item) == name


def test_spawns_within_the_radius_of_a_spot_are_one_spot() -> None:
    r = ip.SPOT_RADIUS
    found = ip.spots([(0, 0), (r / 2, 0), (3 * r, 0), (0, r / 4)])

    assert [n for _, _, n in found] == [3, 1]
    assert found[0][:2] == pytest.approx((r / 6, r / 12))


DATA = {
    "items": {
        "534660031": {"n": "Soul: Airon (Bound)", "npc": [2, 1]},
        "534660001": {"n": "Soul: Krall Laborer (Bound)", "npc": [3]},
        "110130002": {"n": "Wisdom Greatsword", "npc": [1, 3]},
    },
    "npcs": {
        "1": {"n": "Smallbeak Airon", "lv": 18, "k": "Feral"},
        "2": {"n": "Hardbeak Airon", "lv": 33, "k": "Feral"},
        "3": {"n": "Krall Laborer", "lv": 12, "k": "Intellect"},
    },
    "monsters": [1, 0, 50, 0, 1, 10, 50, 0, 2, 1000, 70, 0, 3, -2040, 10, 2040],
}


def test_each_soul_is_a_pet_with_its_monsters_and_spots_lowest_level_first() -> None:
    pets = ip.pets(DATA)

    assert [p["name"] for p in pets] == ["Krall Laborer", "Airon"]
    krall, airon = pets
    assert krall["id"] == "534660001"
    assert krall["genus"] == "cogni"
    assert krall["spots"] == [[25.0, 75.0, 1]]
    assert airon["genus"] == "fera"
    assert airon["monsters"] == [
        {"name": "Smallbeak Airon", "level": 18},
        {"name": "Hardbeak Airon", "level": 33},
    ]
    assert [n for *_, n in airon["spots"]] == [1, 2]  # Hardbeak first, as the soul lists it


def test_a_pet_whose_monsters_are_of_two_genera_is_refused() -> None:
    data = {**DATA, "npcs": {**DATA["npcs"], "2": {"n": "Odd Airon", "lv": 33, "k": "Nature"}}}

    with pytest.raises(ValueError, match="Airon"):
        ip.pets(data)


def test_the_file_reads_back_with_a_pet_to_a_line() -> None:
    doc = ip.document("altgard", DATA)

    text = ip.dumped(doc)

    assert json.loads(text) == doc
    assert len(text.splitlines()) == 4 + len(doc["pets"]) + 2
