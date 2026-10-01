"""The Cubes switch puts the hidden cubes of the route's map over the game, in a ring each.

The cubes come from the map's bundled object set, so a route on Altgard brings Altgard's. The
overlay is handed none while the switch is off, and the ring's radius follows the slider.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

ROUTE = "gold"
CUBES = [(10.0, 20.0), (50.0, 50.0)]  # percent of the map
A_SET = {
    "mapName": "Altgard",
    "categories": [
        {"id": "hidden-cube-altgard", "name": "Hidden Cube", "color": "#eab308"},
        {"id": "teleports", "name": "Teleports", "color": "#16a34a"},
    ],
    "nodes": [
        *({"categoryId": "hidden-cube-altgard", "x": x, "y": y} for x, y in CUBES),
        {"categoryId": "teleports", "x": 70, "y": 70},
    ],
}


@pytest.fixture
def shipped_set(test_maps_root: Callable[[], Path]) -> Iterator[Path]:
    path = test_maps_root().parent / "object-sets" / "altgard.json"
    atomic_write_json(path, A_SET)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs, shipped_set: Path) -> Iterator[Backend]:
    doc = routes.new_route_doc("Gold", "altgard", [1000, 800])
    doc["markers"] = [{"x": 100.0, "y": 100.0}, {"x": 300.0, "y": 200.0}]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        yield made
    finally:
        made.shutdown()


def drawn(backend: Backend) -> int:
    cubes = backend.overlay._cubes
    return 0 if cubes is None else len(cubes)


def test_no_cubes_are_drawn_until_the_switch_is_on(backend: Backend) -> None:
    assert not backend.settings.show_cubes
    assert drawn(backend) == 0


def test_the_switch_brings_every_cube_of_the_map(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_cubes": True}))

    meta = backend._map_meta("altgard")
    cubes = backend.overlay._cubes
    assert meta is not None and cubes is not None
    w, h = meta["size"]
    expected = [c for x, y in CUBES for c in (x / 100 * w, y / 100 * h)]
    assert cubes.ravel().tolist() == pytest.approx(expected)
    assert backend.overlay._cube_radius == 20

    backend.updateSettings(json.dumps({"show_cubes": False}))
    assert drawn(backend) == 0


def test_the_ring_follows_the_slider(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_cubes": True, "cube_radius": 45}))

    assert backend.overlay._cube_radius == 45


def test_the_arrows_switch_leaves_the_cubes_alone(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_cubes": True}))
    backend.setOverlayVisible(False)

    assert not backend.overlay._route_on
    assert drawn(backend) == len(CUBES)
