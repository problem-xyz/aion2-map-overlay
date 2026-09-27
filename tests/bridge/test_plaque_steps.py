"""The steps plaque's arrows tick the next point off by hand and take the last one back.

They used to go to the previous and the next route; a player walking a route wants to correct
the count instead -- a point skipped on purpose, or one ticked off by walking past it. Progress
always counts, so the arrows are always offered.
"""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

ROUTE = "gold"


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    doc = routes.new_route_doc("Gold", "altgard", [1000, 800])
    doc["markers"] = [{"x": 100.0, "y": 100.0}, {"x": 300.0, "y": 200.0}, {"x": 500.0, "y": 300.0}]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        yield made
    finally:
        made.shutdown()


def press(backend: Backend, name: str) -> None:
    backend.steps.actionClicked.emit(name)


def plaque(backend: Backend) -> dict:
    return json.loads(backend.steps.data_json())


def test_the_arrows_are_offered(backend: Backend) -> None:
    assert plaque(backend)["switch"] is True


def test_next_ticks_a_point_off_and_prev_takes_it_back(backend: Backend) -> None:
    ticks: list[str] = []
    backend.progressChanged.connect(ticks.append)

    press(backend, "next")
    press(backend, "next")
    assert plaque(backend)["done"] == 2

    press(backend, "prev")
    assert plaque(backend)["done"] == 1
    assert backend.state.route == ROUTE  # the route stays open
    # the panel hears of every change, as it does of a point reached on foot
    assert [json.loads(t)["done"] for t in ticks] == [1, 2, 1]


def test_the_count_stays_within_the_route(backend: Backend) -> None:

    press(backend, "prev")
    assert plaque(backend)["done"] == 0

    for _ in range(5):
        press(backend, "next")
    assert plaque(backend)["done"] == 3
