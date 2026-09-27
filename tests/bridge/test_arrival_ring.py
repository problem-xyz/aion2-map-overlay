"""The dashed arrival ring on the overlay follows the "mark points on arrival" switch.

The ring marks where a point ticks itself off, and with auto marking off nothing ticks off. The
preview's crosshair is left out in that state too (vision/engine.py).

The overlay draws no ring while its radius is 0 (`OverlayWindow._draw_target`), so that radius
is what these tests read.
"""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

ROUTE = "gold"
MAP_WIDTH = 1000


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    doc = routes.new_route_doc("Gold", "altgard", [MAP_WIDTH, 800])
    doc["markers"] = [{"x": 100.0, "y": 100.0}, {"x": 300.0, "y": 200.0}]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        yield made
    finally:
        made.shutdown()


def set_auto(backend: Backend, on: bool) -> None:
    backend.updateSettings(json.dumps({"auto_progress": on}))


def test_the_ring_is_drawn_at_the_shipped_defaults(backend: Backend) -> None:
    assert backend.settings.auto_progress
    assert backend.overlay._radius == pytest.approx(backend.settings.arrive_radius * MAP_WIDTH)


def test_the_ring_comes_and_goes_with_the_switch(backend: Backend) -> None:
    set_auto(backend, False)
    assert backend.overlay._radius == 0

    set_auto(backend, True)
    assert backend.overlay._radius == pytest.approx(backend.settings.arrive_radius * MAP_WIDTH)


def test_a_new_radius_stays_hidden_while_auto_marking_is_off(backend: Backend) -> None:
    set_auto(backend, False)
    backend.updateSettings(json.dumps({"arrive_radius": 32 / 4096}))

    assert backend.overlay._radius == 0
