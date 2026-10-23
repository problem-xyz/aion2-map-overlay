"""store/pets.py: the bundled pets of each map, and the spots of those picked in map pixels."""

import json
import math
from pathlib import Path

import pytest

from map_overlay.store.pets import (
    BEST_AREA,
    MAX_PICKED,
    best_points,
    best_spot,
    level_key,
    pet_points,
    pets_of,
    portrait,
)

REPO = Path(__file__).resolve().parents[2]

GENERA = {"cogni", "fera", "natura", "varian"}


@pytest.mark.parametrize(("map_id", "count"), [("altgard", 108), ("verteron", 113)])
def test_each_map_has_the_pets_its_soul_items_name(map_id: str, count: int) -> None:
    pets = pets_of(map_id)

    assert len(pets) == count
    assert len({p["id"] for p in pets}) == count
    for pet in pets:
        assert pet["genus"] in GENERA
        assert pet["monsters"], pet["name"]
        assert pet["spots"], pet["name"]
        for x, y, n in pet["spots"]:
            assert 0 <= x <= 100
            assert 0 <= y <= 100
            assert n >= 1


def test_a_map_without_pets_has_none() -> None:
    assert pets_of("nowhere") == []


def test_the_spots_are_in_map_pixels_in_the_order_picked() -> None:
    first, second = pets_of("altgard")[:2]

    points = pet_points("altgard", (1000, 500), [second["id"], first["id"]])

    assert list(points) == [second["id"], first["id"]]
    x, y, _ = first["spots"][0]
    assert points[first["id"]][0] == pytest.approx((x * 10, y * 5))
    assert len(points[first["id"]]) == len(first["spots"])


def test_a_pet_the_map_has_not_is_left_out() -> None:
    pet = pets_of("altgard")[0]

    assert list(pet_points("altgard", (100, 100), ["no-such-pet", pet["id"]])) == [pet["id"]]


def test_no_more_than_max_picked_are_given() -> None:
    ids = [p["id"] for p in pets_of("verteron")[: MAX_PICKED + 2]]

    assert list(pet_points("verteron", (100, 100), ids)) == ids[:MAX_PICKED]


def test_a_level_is_kept_by_map_and_pet() -> None:
    assert level_key("altgard", "534660047") == "altgard:534660047"


def test_a_pet_with_a_portrait_has_it_square_and_one_without_has_none() -> None:
    index = json.loads((REPO / "assets" / "pets" / "portraits.json").read_text(encoding="utf-8"))

    face = portrait(index["ids"][0])

    assert face is not None
    assert face.shape == (index["cell"], index["cell"], 3)
    assert portrait("no-such-pet") is None


def test_every_portrait_is_of_a_pet_there_is() -> None:
    index = json.loads((REPO / "assets" / "pets" / "portraits.json").read_text(encoding="utf-8"))
    pets = {p["id"] for m in ("altgard", "verteron") for p in pets_of(m)}

    assert set(index["ids"]) <= pets
    assert len(set(index["ids"])) == len(index["ids"])


def own_about(pet: dict, x: float, y: float) -> int:
    """The pet's monsters within a round of (x, y), measured from each of its spots."""
    return sum(n for sx, sy, n in pet["spots"] if math.hypot(sx - x, sy - y) <= BEST_AREA)


def test_the_best_spot_has_nearly_the_most_of_the_pets_monsters() -> None:
    for pet in pets_of("altgard")[:20]:
        found = best_spot("altgard", pet["id"])
        assert found is not None, pet["name"]
        x, y = found
        assert 0 <= x <= 100 and 0 <= y <= 100
        most = max(own_about(pet, sx, sy) for sx, sy, _ in pet["spots"])
        # measured from the middle of the place rather than from a spot, so a camp at its rim may
        # fall outside: the share the place was chosen with, less a margin for that
        assert own_about(pet, x, y) >= 0.6 * most, pet["name"]


def test_a_pet_the_map_has_not_has_no_best_spot() -> None:
    assert best_spot("altgard", "no-such-pet") is None


def test_the_best_spots_are_in_map_pixels_by_pet() -> None:
    pet = pets_of("altgard")[0]
    found = best_spot("altgard", pet["id"])
    assert found is not None

    points = best_points("altgard", (1000, 500), [pet["id"], "no-such-pet"], {})

    assert list(points) == [pet["id"]]
    assert points[pet["id"]] == pytest.approx((found[0] * 10, found[1] * 5))


def test_a_pet_at_the_last_level_does_not_count_toward_anothers_best_spot() -> None:
    pets = pets_of("altgard")
    pet = next(p for p in pets if p["name"] == "Aberrant Bee")
    done = {level_key("altgard", p["id"]): 3 for p in pets if p["id"] != pet["id"]}

    alone = best_spot("altgard", pet["id"], done)
    assert alone is not None
    x, y = alone
    most = max(own_about(pet, sx, sy) for sx, sy, _ in pet["spots"])
    assert own_about(pet, x, y) >= 0.6 * most
