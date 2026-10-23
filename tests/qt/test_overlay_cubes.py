"""The map's hidden cubes over the game, each in a ring of a set radius.

They are the map's and not the route's, so nothing the route does takes them away: a route run
to its end, a view cut to the next steps, the Arrows switch off. What is pinned here is where the
pixels land, on a black frame with the transform the identity.
"""

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from map_overlay.qt.overlay import OverlayWindow
from map_overlay.store.objects import cube_points, cube_tints

SIZE = 200
CUBE = (60.0, 60.0)
RADIUS = 30


@pytest.fixture
def overlay(qapp: QApplication) -> Iterator[OverlayWindow]:
    window = OverlayWindow()
    window._ui_scale = 1.0  # the pixels below are at 100% Windows scale
    window.resize(SIZE, SIZE)
    window.set_opacity(1.0)
    window.set_cubes([CUBE], RADIUS)
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
    return image.pixelColor(int(x), int(y)).red() > 60


def test_a_cube_is_drawn_in_a_ring_of_the_radius_set(overlay: OverlayWindow) -> None:
    image = frame(overlay)

    x, y = CUBE
    assert lit(image, x, y)  # the cube
    assert lit(image, x + RADIUS, y)  # the ring
    assert not lit(image, x + RADIUS + 6, y)  # nothing past it


def test_the_radius_follows_the_setting(overlay: OverlayWindow) -> None:
    overlay.set_cubes([CUBE], 50)
    image = frame(overlay)

    x, y = CUBE
    assert not lit(image, x + RADIUS, y + 0.5)
    assert lit(image, x + 50, y)


def test_cubes_stay_with_the_route_finished_and_the_arrows_off(overlay: OverlayWindow) -> None:
    overlay.set_route(
        {
            "markers": [{"x": 150.0, "y": 150.0, "text": ""}, {"x": 180.0, "y": 150.0, "text": ""}],
            "style": {"color": "#ffffff", "width": 3},
            "mapSize": [SIZE, SIZE],
        },
        (SIZE, SIZE),
    )
    overlay.set_transform(np.eye(3))
    overlay.set_progress(2)
    overlay.set_route_visible(False)

    assert lit(frame(overlay), *CUBE)


def test_the_arrows_off_leave_the_route_out(overlay: OverlayWindow) -> None:
    overlay.set_cubes([], RADIUS)
    overlay.set_route(
        {
            "markers": [{"x": 20.0, "y": 150.0, "text": ""}, {"x": 180.0, "y": 150.0, "text": ""}],
            "style": {"color": "#ffffff", "width": 3},
            "mapSize": [SIZE, SIZE],
        },
        (SIZE, SIZE),
    )
    overlay.set_transform(np.eye(3))
    assert lit(frame(overlay), 60, 150)

    overlay.set_route_visible(False)
    assert not lit(frame(overlay), 60, 150)


def test_cube_points_are_the_hidden_cubes_in_map_pixels() -> None:
    sets = [
        {
            "mapName": "Verteron",
            "categories": [{"id": "hidden-cube-verteron"}, {"id": "teleports"}],
            "nodes": [
                {"c": "hidden-cube-verteron", "x": 25.0, "y": 50.0},
                {"c": "hidden-cube-verteron", "x": 50.0, "y": 25.0, "l": -1, "g": 2},
                {"c": "teleports", "x": 10.0, "y": 10.0},
            ],
        }
    ]

    assert cube_points(sets, (4096, 2048)) == [(1024.0, 1024.0, 0, 0), (2048.0, 512.0, -1, 2)]


def test_a_cube_is_painted_in_its_group_s_tint(overlay: OverlayWindow) -> None:
    sky = QColor(cube_tints()[2]["left"])
    overlay.set_cubes([(*CUBE, 0, 2)], 0)

    # the left face, below and left of the middle
    face = frame(overlay).pixelColor(int(CUBE[0] - 4), int(CUBE[1] + 4))

    assert (face.red(), face.green(), face.blue()) == (sky.red(), sky.green(), sky.blue())


def test_a_tint_past_the_palette_is_painted_coral(overlay: OverlayWindow) -> None:
    coral = QColor(cube_tints()[0]["left"])
    overlay.set_cubes([(*CUBE, 0, 99)], 0)

    face = frame(overlay).pixelColor(int(CUBE[0] - 4), int(CUBE[1] + 4))

    assert (face.red(), face.green(), face.blue()) == (coral.red(), coral.green(), coral.blue())


# Where the arrow beside the cube falls: right of it, at its top corner for up, its bottom for down.
ABOVE = (CUBE[0] + 13, CUBE[1] - 6)
BELOW = (CUBE[0] + 13, CUBE[1] + 6)


def test_a_cube_on_the_ground_has_no_arrow(overlay: OverlayWindow) -> None:
    image = frame(overlay)

    assert not lit(image, *ABOVE)
    assert not lit(image, *BELOW)


@pytest.mark.parametrize(("level", "at", "not_at"), [(1, ABOVE, BELOW), (-1, BELOW, ABOVE)])
def test_a_cube_above_or_below_the_ground_has_an_arrow_beside_it(
    overlay: OverlayWindow, level: int, at: tuple[float, float], not_at: tuple[float, float]
) -> None:
    overlay.set_cubes([(*CUBE, level)], RADIUS)
    image = frame(overlay)

    assert lit(image, *at)
    assert not lit(image, *not_at)


def test_the_cube_and_its_ring_grow_with_the_windows_scale(qapp: QApplication) -> None:
    window = OverlayWindow()
    window.resize(SIZE, SIZE)
    window.set_opacity(1.0)
    window._ui_scale = 1.5
    window.set_cubes([CUBE], RADIUS)
    window.set_transform(np.eye(3))
    try:
        image = frame(window)
    finally:
        window.deleteLater()

    x, y = CUBE
    assert lit(image, x + 11, y)  # the cube's right face, past where it ends at 100%
    assert lit(image, x + RADIUS * 1.5, y)  # the ring
    assert not lit(image, x + RADIUS, y + 0.5)
