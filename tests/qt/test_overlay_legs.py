"""The overlay colours each leg of the route by the point it leads to.

Running to a side quest, the line and its arrow are green as the point is; to the end of the
route, teal. The colour of a leg follows progress: with points passed, the first leg left is
still the one that leads to the next point.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import END_COLOR, OverlayWindow

GREEN = "#22c55e"
BLUE = "#6ea8ff"
ROUTE = "#f2b544"


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window.set_route(
        {
            "markers": [
                {"x": 0.0, "y": 0.0, "text": ""},
                {"x": 10.0, "y": 0.0, "text": "", "color": GREEN},
                {"x": 20.0, "y": 0.0, "text": ""},
                {"x": 30.0, "y": 0.0, "text": "", "color": BLUE},
                {"x": 40.0, "y": 0.0, "text": ""},
            ],
            "style": {"color": ROUTE, "width": 3},
            "mapSize": [100, 100],
        }
    )
    try:
        yield window
    finally:
        window.deleteLater()


def colours(overlay: OverlayWindow, legs: int) -> list[str]:
    return [overlay.leg_color(leg).name() for leg in range(legs)]


def test_each_leg_takes_the_colour_of_the_point_it_leads_to(overlay: OverlayWindow) -> None:
    # into the green point, into a plain one, into the blue one, into the end
    assert colours(overlay, 4) == [GREEN, ROUTE, BLUE, END_COLOR.name()]


def test_the_legs_left_keep_their_colours_as_points_are_passed(overlay: OverlayWindow) -> None:
    overlay.set_progress(2)

    # two points passed: the first leg left leads into the blue point
    assert colours(overlay, 2) == [BLUE, END_COLOR.name()]
