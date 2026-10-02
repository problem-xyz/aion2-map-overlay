"""The gathering points over the game, each its resource's mark on a dark disc.

What is pinned here is where the pixels land, on a black frame with the transform the identity,
and that the marks are the map's, as the cubes are: the Arrows switch does not take them away.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import RESOURCE_HALF, OverlayWindow

SIZE = 200
ORE = (60.0, 60.0)
RUBY = (140.0, 60.0)


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window.resize(SIZE, SIZE)
    window.set_opacity(1.0)
    window.set_resources({"orichalcum": [ORE], "ruby": [RUBY]})
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


def test_each_point_is_drawn_where_it_stands_and_nothing_past_its_mark(
    overlay: OverlayWindow,
) -> None:
    image = frame(overlay)

    for x, y in (ORE, RUBY):
        assert lit(image, x, y)
        assert not lit(image, x + RESOURCE_HALF + 3, y)
    assert not lit(image, 100, 60)


def test_each_resource_is_drawn_in_its_own_colours(overlay: OverlayWindow) -> None:
    image = frame(overlay)

    ore = image.pixelColor(int(ORE[0]), int(ORE[1]))
    ruby = image.pixelColor(int(RUBY[0]), int(RUBY[1]))
    assert ore != ruby
    assert ruby.red() > ruby.blue()


def test_the_arrows_off_leave_the_resources_drawn(overlay: OverlayWindow) -> None:
    overlay.set_route_visible(False)

    assert lit(frame(overlay), *ORE)


def test_no_resources_draws_none(overlay: OverlayWindow) -> None:
    overlay.set_resources({})

    image = frame(overlay)
    assert not lit(image, *ORE)
    assert not lit(image, *RUBY)


def test_a_resource_with_no_drawing_is_left_out(overlay: OverlayWindow) -> None:
    overlay.set_resources({"no-such-resource": [ORE]})

    assert not lit(frame(overlay), *ORE)
