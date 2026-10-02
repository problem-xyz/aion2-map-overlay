"""The Resources switch puts the gathering points of the resources picked over the game.

Like the cubes they come from the map's bundled object set and stay whatever the route does; the
list of resources picked is kept while the switch is off, and the map tells the panel which
resources it has.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

ROUTE = "gold"
ORE = [(10.0, 20.0), (50.0, 50.0)]  # percent of the map
RUBY = [(30.0, 40.0)]
A_SET = {
    "mapName": "Altgard",
    "categories": [
        {"id": "gathering", "name": "Gathering"},
        {"id": "gathering-orichalcum", "name": "Orichalcum", "parentId": "gathering"},
        {"id": "gathering-ruby", "name": "Ruby", "parentId": "gathering"},
        {"id": "teleports", "name": "Teleports", "color": "#16a34a"},
    ],
    "nodes": [
        *({"categoryId": "gathering-orichalcum", "x": x, "y": y} for x, y in ORE),
        *({"categoryId": "gathering-ruby", "x": x, "y": y} for x, y in RUBY),
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


def drawn(backend: Backend) -> dict[str, int]:
    return {rid: len(points) for rid, points in backend.overlay._resources.items()}


def test_nothing_is_drawn_until_the_switch_is_on(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"resources": ["orichalcum"]}))

    assert not backend.settings.show_resources
    assert drawn(backend) == {}


def test_the_switch_brings_the_points_of_the_resources_picked(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_resources": True, "resources": ["orichalcum"]}))

    meta = backend._map_meta("altgard")
    assert meta is not None
    w, h = meta["size"]
    ore = backend.overlay._resources["orichalcum"]
    assert ore.ravel().tolist() == pytest.approx(
        [c for x, y in ORE for c in (x / 100 * w, y / 100 * h)]
    )
    assert drawn(backend) == {"orichalcum": 2}

    backend.updateSettings(json.dumps({"resources": ["orichalcum", "ruby"]}))
    assert drawn(backend) == {"orichalcum": 2, "ruby": 1}

    backend.updateSettings(json.dumps({"show_resources": False}))
    assert drawn(backend) == {}
    assert backend.settings.resources == ["orichalcum", "ruby"]  # kept for the next time


def test_a_resource_the_map_has_none_of_draws_nothing(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_resources": True, "resources": ["aria"]}))

    assert drawn(backend) == {}
    assert backend._picked_resources() == []


def test_the_arrows_switch_leaves_the_resources_alone(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_resources": True, "resources": ["ruby"]}))
    backend.setOverlayVisible(False)

    assert not backend.overlay._route_on
    assert drawn(backend) == {"ruby": 1}
    assert backend._overlay_wanted()


def test_the_map_lists_the_resources_it_has_in_the_catalogs_order(backend: Backend) -> None:
    maps = {m["id"]: m for m in json.loads(backend.getState())["maps"]}

    assert maps["altgard"]["resources"] == ["orichalcum", "ruby"]
    assert maps["verteron"]["resources"] == []


@pytest.fixture
def no_route(qapp: QApplication, dirs: DataDirs, shipped_set: Path) -> Iterator[Backend]:
    made = Backend(dirs)
    made._store.set_state(region={"left": 0, "top": 0, "width": 200, "height": 200})
    made._revalidate_screens = lambda: False
    try:
        yield made
    finally:
        made.shutdown()


def record_start(backend: Backend, monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    starts: list[dict[str, Any]] = []
    monkeypatch.setattr(backend.engine, "start", lambda **config: starts.append(config))
    return starts


def test_with_resources_picked_a_start_with_no_route_asks_the_map_and_runs_on_it(
    no_route: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = record_start(no_route, monkeypatch)
    monkeypatch.setattr(no_route._dialogs, "ask_choice", lambda *_: "Altgard")
    no_route.updateSettings(json.dumps({"show_resources": True, "resources": ["ruby"]}))

    no_route.start()

    assert len(starts) == 1
    assert Path(starts[0]["reference"]).parent.name == "altgard"
    assert drawn(no_route) == {"ruby": 1}


def test_the_switch_on_with_nothing_picked_does_not_start_without_a_route(
    no_route: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = record_start(no_route, monkeypatch)
    monkeypatch.setattr(no_route._dialogs, "ask_choice", lambda *_: pytest.fail("asked"))
    no_route.updateSettings(json.dumps({"show_resources": True}))

    no_route.start()

    assert starts == []
