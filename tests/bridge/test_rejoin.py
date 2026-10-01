"""Off the route and at a later point of it, the player is asked whether to go on from there.

They may have lost the route and walked on past points they did not tick off. A yes ticks off
everything up to the point they stand at; a no is not asked again about that point. Only off
the route: on it, points are ticked off in their order and in no other, as ever.
"""

import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.progress import rejoin_at
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

MAP = 4096
# A route that goes east, then far south and back: points 3 and 4 lie away from the first leg.
MARKERS = [
    {"x": 1000.0, "y": 1000.0},
    {"x": 1200.0, "y": 1000.0},
    {"x": 1200.0, "y": 2000.0},
    {"x": 1400.0, "y": 2000.0},
    {"x": 1600.0, "y": 1000.0},
]
DOC = {"mapSize": [MAP, MAP], "markers": MARKERS}
SIZE = (MAP, MAP)
RADIUS = 8 / 4096  # the shipped arrival radius, as a share of the map's width


def test_the_first_later_point_stood_at_is_the_one() -> None:
    assert rejoin_at(1200, 2003, DOC, 1, SIZE, radius=RADIUS) == 2
    assert rejoin_at(1400, 2000, DOC, 1, SIZE, radius=RADIUS) == 3


def test_neither_the_next_point_nor_one_passed_counts() -> None:
    # the next point is ticked off the usual way; one behind is not where the route goes on
    assert rejoin_at(1200, 1000, DOC, 1, SIZE, radius=RADIUS) is None
    assert rejoin_at(1000, 1000, DOC, 2, SIZE, radius=RADIUS) is None


def test_away_from_every_point_there_is_nothing_to_go_on_from() -> None:
    assert rejoin_at(3000, 3000, DOC, 0, SIZE, radius=RADIUS) is None


# ------------------------------------------------------------------ the backend's part

ROUTE = "lost"
REGION = {"left": 0, "top": 0, "width": 400, "height": 400}


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    doc = routes.new_route_doc("Lost", "altgard", [MAP, MAP])
    doc["markers"] = MARKERS
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    made._store.set_state(region=REGION)
    try:
        made.setRoute(ROUTE)
        made.setProgress(1)  # point 1 passed, on the way to point 2
        yield made
    finally:
        made.shutdown()


def at(backend: Backend, x: float, y: float) -> None:
    """The player at (x, y) in route pixels, given as the engine does, in reference pixels."""
    meta = backend._map_meta("altgard")
    assert meta is not None
    w, h = meta["size"]
    backend._on_player(x * w / MAP, y * h / MAP)


def en(key: str) -> str:
    catalog = json.loads(Path("locales/en.json").read_text(encoding="utf-8"))
    node = catalog
    for part in key.split("."):
        node = node[part]
    return node


def test_at_a_later_point_off_the_route_the_player_is_asked(backend: Backend) -> None:
    at(backend, 1400, 2000)  # point 4, far off the leg from point 1 to point 2

    prompt = backend._windows.prompt
    assert prompt.asking()
    assert prompt._title.text() == en("native.prompt.rejoinTitle").format(n=4)
    assert prompt._detail.text() == en("native.prompt.rejoinMany").format(first=2, last=3)
    assert backend._state()["progress"]["done"] == 1  # nothing changes until they answer


def test_yes_goes_on_from_that_point(backend: Backend) -> None:
    at(backend, 1400, 2000)
    backend._windows.prompt._yes.click()

    assert backend._state()["progress"]["done"] == 4
    assert not backend._windows.prompt.asking()
    assert backend.overlay._far is None  # on the route again, the leg from point 4 to point 5


def test_no_is_not_asked_again_about_that_point(backend: Backend) -> None:
    at(backend, 1400, 2000)
    backend._windows.prompt._no.click()
    at(backend, 1400, 2001)

    assert not backend._windows.prompt.asking()
    assert backend._state()["progress"]["done"] == 1


def test_one_point_skipped_says_so_in_the_singular(backend: Backend) -> None:
    at(backend, 1200, 2000)  # point 3: only point 2 is skipped

    assert backend._windows.prompt._detail.text() == en("native.prompt.rejoinOne").format(first=2)


def test_back_on_the_route_the_question_goes(backend: Backend) -> None:
    at(backend, 1400, 2000)
    at(backend, 1100, 1000)  # on the leg being walked again

    assert not backend._windows.prompt.asking()


def test_the_strip_under_the_question_gives_way_to_it(backend: Backend) -> None:
    backend.overlay.set_transform(np.eye(3))  # the map found: the strip is drawn over it
    at(backend, 1400, 2000)
    assert backend.overlay._covered == backend._windows.prompt.height()
    assert backend.overlay._notice() is None  # the strip it covers is not drawn

    backend._windows.prompt._no.click()
    assert backend.overlay._covered == 0
    assert backend.overlay._notice() is not None  # still off the route, and saying so
