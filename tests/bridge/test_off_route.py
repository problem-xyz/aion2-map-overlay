"""Far off the route, the overlay says so: which point is next, and which way it lies.

Far off is measured from the leg being walked -- the last point passed to the next one -- so a
long leg walked end to end is never off the route. The overlay stops saying it a little nearer
than it started, so a player on the edge does not make the strip blink.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.progress import BACK_ON_ROUTE, FAR_FROM_ROUTE, compass, off_route
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

MAP = 4096
DOC = {
    "mapSize": [MAP, MAP],
    "markers": [{"x": 1000.0, "y": 1000.0}, {"x": 2000.0, "y": 1000.0}, {"x": 2000.0, "y": 2000.0}],
}
SIZE = (MAP, MAP)  # the reference the same size as the route's map: positions read alike
FAR = FAR_FROM_ROUTE * MAP
BACK = BACK_ON_ROUTE * MAP


def test_on_the_leg_being_walked_is_on_the_route_however_long_it_is() -> None:
    # point 1 passed, walking to point 2, halfway along and a little to the side
    assert off_route(1500, 1000 + FAR - 1, DOC, 1, SIZE) is None


def test_far_off_the_leg_names_the_next_point_and_the_way_to_it() -> None:
    assert off_route(1900, 1000 + FAR + 10, DOC, 1, SIZE) == (1, "ne")


def test_before_any_point_is_passed_the_first_one_is_what_counts() -> None:
    assert off_route(1000, 1000 + FAR - 1, DOC, 0, SIZE) is None
    assert off_route(1000 + FAR + 10, 1000, DOC, 0, SIZE) == (0, "w")


def test_a_player_already_off_has_to_come_nearer_to_be_back() -> None:
    between = 1000 + (FAR + BACK) / 2
    assert off_route(1500, between, DOC, 1, SIZE) is None
    assert off_route(1500, between, DOC, 1, SIZE, was_off=True) is not None
    assert off_route(1500, 1000 + BACK - 1, DOC, 1, SIZE, was_off=True) is None


def test_a_finished_route_has_nothing_to_be_off() -> None:
    assert off_route(0, 0, DOC, len(DOC["markers"]), SIZE) is None


def test_a_reference_of_another_size_is_scaled_onto_the_route() -> None:
    # the same far spot, given in the pixels of a reference half the size
    assert off_route(950, (1000 + FAR + 10) / 2, DOC, 1, (MAP / 2, MAP / 2)) == (1, "ne")


@pytest.mark.parametrize(
    ("dx", "dy", "way"),
    [(0, -1, "n"), (1, -1, "ne"), (1, 0, "e"), (1, 1, "se"), (0, 1, "s"), (-1, 0, "w")],
)
def test_the_compass_has_north_up_and_y_growing_south(dx: int, dy: int, way: str) -> None:
    assert compass(dx, dy) == way


# ------------------------------------------------------------------ the backend's part

ROUTE = "far"


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    doc = routes.new_route_doc("Far", "altgard", [MAP, MAP])
    doc["markers"] = DOC["markers"]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        made.setProgress(1)
        yield made
    finally:
        made.shutdown()


def at(backend: Backend, x: float, y: float) -> None:
    """The player at (x, y) in route pixels, given as the engine does, in reference pixels."""
    meta = backend._map_meta("altgard")
    assert meta is not None
    w, h = meta["size"]
    backend._on_player(x * w / MAP, y * h / MAP)


def test_far_off_the_overlay_says_which_point_and_which_way(backend: Backend) -> None:
    at(backend, 1900, 1000 + FAR + 50)

    assert backend.overlay._far is not None
    title, detail = backend.overlay._far
    en = json.loads(Path("locales/en.json").read_text(encoding="utf-8"))["native"]["overlay"]
    assert title == en["farTitle"]
    assert detail == en["far"].format(n=2, way=en["way"]["ne"])


def test_back_on_the_route_the_strip_goes(backend: Backend) -> None:
    at(backend, 1900, 1000 + FAR + 50)
    at(backend, 1500, 1000)

    assert backend.overlay._far is None


def test_a_point_ticked_off_by_hand_takes_the_strip_with_it(backend: Backend) -> None:
    at(backend, 1900, 1000 + FAR + 50)
    backend.setProgress(2)

    assert backend.overlay._far is None


def test_with_the_hints_off_nothing_is_said_off_the_route(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"route_far_notice": False}))

    at(backend, 1900, 1000 + FAR + 50)

    assert backend.overlay._far is None


def test_turning_the_hints_off_takes_the_strip_away_at_once(backend: Backend) -> None:
    at(backend, 1900, 1000 + FAR + 50)
    assert backend.overlay._far is not None

    backend.updateSettings(json.dumps({"route_far_notice": False}))

    assert backend.overlay._far is None


def test_with_the_route_mode_off_there_is_no_route_to_be_off(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"route_mode": False}))

    at(backend, 1900, 1000 + FAR + 50)

    assert backend.overlay._far is None
    assert backend.overlay._pts is None  # the route is not drawn
    assert backend.route == ROUTE  # but stays chosen

    backend.updateSettings(json.dumps({"route_mode": True}))
    assert backend.overlay._pts is not None
