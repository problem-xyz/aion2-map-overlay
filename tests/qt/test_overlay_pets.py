"""The pets' spots over the game, each a paw on a disc of the pet's colour.

What is pinned here is where the pixels land, on a black frame with the transform the identity,
that a pet's colour is its place among those picked, as the panel shows it, and that a pet the
game has a portrait of shows it inside its ring.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import (
    PET_BEST_HALF,
    PET_COLORS,
    PET_HALF,
    PET_PAW,
    PET_STAR,
    PET_STAR_FILL,
    OverlayWindow,
)

REPO = Path(__file__).resolve().parents[2]

SIZE = 200
FIRST = (60.0, 60.0)
SECOND = (140.0, 60.0)


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window._ui_scale = 1.0  # the pixels below are at 100% Windows scale
    window.resize(SIZE, SIZE)
    window.set_opacity(1.0)
    window.set_pets({"a": [FIRST], "b": [SECOND]})
    window.set_transform(np.eye(3))
    try:
        yield window
    finally:
        window.deleteLater()


def frame(overlay: OverlayWindow) -> QImage:
    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    painter = QPainter(image)
    overlay.render(painter, QPoint(0, 0))
    painter.end()
    return image


def lit(image: QImage, x: float, y: float) -> bool:
    c = image.pixelColor(int(x), int(y))
    return max(c.red(), c.green(), c.blue()) > 60


def near(a: QColor, b: QColor) -> bool:
    return max(abs(a.red() - b.red()), abs(a.green() - b.green()), abs(a.blue() - b.blue())) < 12


def test_each_spot_is_drawn_where_it_stands_and_nothing_past_its_disc(
    overlay: OverlayWindow,
) -> None:
    image = frame(overlay)

    for x, y in (FIRST, SECOND):
        assert lit(image, x - PET_HALF + 3, y)
        assert not lit(image, x + PET_HALF + 3, y)
    assert not lit(image, 100, 60)


def test_each_pet_is_drawn_in_the_colour_of_its_place(overlay: OverlayWindow) -> None:
    image = frame(overlay)

    # the disc's rim, left of the paw
    assert near(image.pixelColor(int(FIRST[0] - PET_HALF + 3), int(FIRST[1])), PET_COLORS[0])
    assert near(image.pixelColor(int(SECOND[0] - PET_HALF + 3), int(SECOND[1])), PET_COLORS[1])


def test_a_pet_with_no_spots_keeps_its_place(overlay: OverlayWindow) -> None:
    overlay.set_pets({"a": [], "b": [SECOND]})

    image = frame(overlay)
    assert not lit(image, *FIRST)
    assert near(image.pixelColor(int(SECOND[0] - PET_HALF + 3), int(SECOND[1])), PET_COLORS[1])


def test_no_pets_draws_none(overlay: OverlayWindow) -> None:
    overlay.set_pets({})

    image = frame(overlay)
    assert not lit(image, *FIRST)
    assert not lit(image, *SECOND)


def test_a_pet_with_a_portrait_shows_it_inside_its_ring(overlay: OverlayWindow) -> None:
    index = json.loads((REPO / "assets" / "pets" / "portraits.json").read_text(encoding="utf-8"))
    overlay.set_pets({index["ids"][0]: [FIRST]})

    image = frame(overlay)

    assert near(image.pixelColor(int(FIRST[0] - PET_HALF + 2), int(FIRST[1])), PET_COLORS[0])
    middle = image.pixelColor(int(FIRST[0]), int(FIRST[1]))
    assert not near(middle, PET_COLORS[0])
    assert not near(middle, PET_PAW)


def test_a_best_spot_is_drawn_larger_with_a_gold_star(overlay: OverlayWindow) -> None:
    best = (100.0, 140.0)
    overlay.set_pets({"a": [FIRST]}, {"a": best})

    image = frame(overlay)

    # larger than a spot: lit past where a spot's disc ends
    assert lit(image, best[0] - PET_BEST_HALF + 3, best[1])
    assert not lit(image, FIRST[0] - PET_HALF - 3, FIRST[1])
    # the star at its top right, in gold: its middle half its size in from the disc's corner
    off = PET_BEST_HALF - PET_STAR / 2
    star = image.pixelColor(int(best[0] + off), int(best[1] - off))
    assert near(star, PET_STAR_FILL)


def test_no_best_spot_without_one(overlay: OverlayWindow) -> None:
    overlay.set_pets({"a": [FIRST]})

    assert overlay._pet_best == [None]
