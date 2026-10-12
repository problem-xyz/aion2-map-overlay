"""The Pets switch puts the spots of the pets picked over the game.

Like the resources they are the map's and stay whatever the route does; the pets picked are kept
while the switch is off, and a pet the map has not draws nothing. The pets are the shipped ones.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes
from map_overlay.store.pets import pets_of

ROUTE = "souls"


@pytest.fixture
def backend(
    qapp: QApplication, dirs: DataDirs, test_maps_root: Callable[[], Path]
) -> Iterator[Backend]:
    doc = routes.new_route_doc("Souls", "altgard", [1000, 800])
    doc["markers"] = [{"x": 100.0, "y": 100.0}, {"x": 300.0, "y": 200.0}]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        yield made
    finally:
        made.shutdown()


def drawn(backend: Backend) -> list[int]:
    return [len(points) for _, points in backend.overlay._pets]


def spots(map_id: str, index: int) -> int:
    return len(pets_of(map_id)[index]["spots"])


def pet(map_id: str, index: int) -> str:
    return pets_of(map_id)[index]["id"]


def test_nothing_is_drawn_until_the_switch_is_on(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"pets": [pet("altgard", 0)]}))

    assert not backend.settings.show_pets
    assert drawn(backend) == []


def test_the_switch_brings_the_spots_of_the_pets_picked(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_pets": True, "pets": [pet("altgard", 0)]}))

    meta = backend._map_meta("altgard")
    assert meta is not None
    w, h = meta["size"]
    x, y, _ = pets_of("altgard")[0]["spots"][0]
    first = backend.overlay._pets[0][1]
    assert first[0].ravel().tolist() == pytest.approx([x / 100 * w, y / 100 * h])
    assert drawn(backend) == [spots("altgard", 0)]

    backend.updateSettings(json.dumps({"pets": [pet("altgard", 1), pet("altgard", 0)]}))
    assert drawn(backend) == [spots("altgard", 1), spots("altgard", 0)]

    backend.updateSettings(json.dumps({"show_pets": False}))
    assert drawn(backend) == []
    assert backend.settings.pets == [pet("altgard", 1), pet("altgard", 0)]  # kept for next time


def test_a_level_set_does_not_redraw_the_spots(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_pets": True, "pets": [pet("altgard", 0)]}))
    before = backend.overlay._pets

    backend.updateSettings(json.dumps({"pet_levels": {f"altgard:{pet('altgard', 0)}": 2}}))

    assert backend.overlay._pets is before


def test_a_pet_the_map_has_none_of_draws_nothing(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_pets": True, "pets": ["no-such-pet"]}))

    assert drawn(backend) == []
    assert not backend._picked_pets()


def test_the_arrows_switch_leaves_the_pets_alone(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"show_pets": True, "pets": [pet("altgard", 0)]}))
    backend.setOverlayVisible(False)

    assert not backend.overlay._route_on
    assert drawn(backend) == [spots("altgard", 0)]
    assert backend._overlay_wanted()


@pytest.fixture
def no_route(
    qapp: QApplication, dirs: DataDirs, test_maps_root: Callable[[], Path]
) -> Iterator[Backend]:
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


def test_with_pets_picked_a_start_with_no_route_draws_the_map_the_engine_finds(
    no_route: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = record_start(no_route, monkeypatch)
    monkeypatch.setattr(no_route._dialogs, "ask_choice", lambda *_: pytest.fail("asked"))
    no_route.updateSettings(json.dumps({"show_pets": True, "pets": [pet("altgard", 0)]}))

    no_route.start()
    assert len(starts) == 1
    assert len(starts[0]["maps"]) == 2
    assert drawn(no_route) == []

    no_route.engine.mapFound.emit(0)  # Altgard
    assert drawn(no_route) == [spots("altgard", 0)]


def test_the_switch_on_with_no_pet_picked_does_not_start_without_a_route(
    no_route: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts = record_start(no_route, monkeypatch)
    monkeypatch.setattr(no_route._dialogs, "ask_choice", lambda *_: pytest.fail("asked"))
    no_route.updateSettings(json.dumps({"show_pets": True}))

    no_route.start()

    assert starts == []
