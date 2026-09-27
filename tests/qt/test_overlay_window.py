"""How much of the route the overlay draws, in each of the three views the settings offer.

"steps": the next steps in full, the last ones passed faded, nothing further either way.
"dim": the whole route, faded away from the next steps. "all": the whole route ahead in full,
what was passed faded. Drawn whole and alike, a route that loops about a village was a tangle
the way on could not be read from. What is pinned here is the split, measured on the pixels of
a zigzag route with every leg white.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import OverlayWindow

WIDTH, HEIGHT = 200, 560
WHITE = "#ffffff"
AHEAD, PAST = 3, 2
DONE = PAST + 2  # more points passed than "steps" draws
POINTS = [(20.0 if i % 2 == 0 else 180.0, 20.0 + i * 40.0) for i in range(13)]
LAST_LEG = len(POINTS) - 2

# the leg being walked, from the last point passed into the next one, and on to the last step
BRIGHT = range(DONE - 1, DONE + AHEAD - 1)
PASSED = range(DONE - PAST, DONE - 1)  # the legs between the steps "steps" keeps


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window.resize(WIDTH, HEIGHT)
    markers = [{"x": x, "y": y, "text": "", "color": WHITE} for x, y in POINTS]
    window.set_route(
        {"markers": markers, "style": {"color": WHITE, "width": 3}, "mapSize": [WIDTH, HEIGHT]},
        (WIDTH, HEIGHT),
    )
    window.set_transform(np.eye(3))
    window.set_progress(DONE)
    try:
        yield window
    finally:
        window.deleteLater()


def frame(overlay: OverlayWindow, mode: str) -> QImage:
    overlay.set_view(mode, AHEAD, PAST)
    image = QImage(WIDTH, HEIGHT, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0))
    painter = QPainter(image)
    overlay.render(painter, QPoint(0, 0))
    painter.end()
    return image


def leg(image: QImage, i: int) -> str:
    """How the leg from point i is drawn, read a quarter of the way along: clear of its chevron."""
    (ax, ay), (bx, by) = POINTS[i], POINTS[i + 1]
    value = image.pixelColor(int(ax + (bx - ax) / 4), int(ay + (by - ay) / 4)).red()
    if value > 180:
        return "bright"
    if value > 30:
        return "faded"
    return "none" if value == 0 else f"unclear {value}"


def test_steps_draws_the_next_steps_bright_the_last_passed_faded_and_nothing_else(
    overlay: OverlayWindow,
) -> None:
    image = frame(overlay, "steps")

    assert [leg(image, i) for i in BRIGHT] == ["bright"] * AHEAD
    assert [leg(image, i) for i in PASSED] == ["faded"] * len(PASSED)
    assert leg(image, DONE - PAST - 1) == "none"
    assert leg(image, DONE + AHEAD - 1) == "none"
    assert leg(image, LAST_LEG) == "none"


def test_dim_draws_the_whole_route_faded_away_from_the_next_steps(
    overlay: OverlayWindow,
) -> None:
    image = frame(overlay, "dim")

    assert [leg(image, i) for i in BRIGHT] == ["bright"] * AHEAD
    assert leg(image, 0) == "faded"
    assert leg(image, DONE + AHEAD - 1) == "faded"
    assert leg(image, LAST_LEG) == "faded"


def test_all_draws_the_whole_route_ahead_bright_and_what_was_passed_faded(
    overlay: OverlayWindow,
) -> None:
    image = frame(overlay, "all")

    assert [leg(image, i) for i in range(DONE - 1, LAST_LEG + 1)] == ["bright"] * (
        LAST_LEG - DONE + 2
    )
    assert leg(image, 0) == "faded"
