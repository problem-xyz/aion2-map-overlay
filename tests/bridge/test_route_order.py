"""The order the panel lists the routes in: the user's, from dragging, with a new route last.

Routes used to be listed by file name, so a new one landed wherever its name sorted -- often
first, above the routes the user had been working through.
"""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes
from map_overlay.store.maps import MapSpec


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def listed(backend: Backend) -> list[str]:
    return [r["id"] for r in json.loads(backend.getState())["routes"]]


def save_new(backend: Backend, map_id: str, name: str) -> str:
    doc = routes.new_route_doc(name, map_id, [512, 384])
    reply = json.loads(backend.saveRoute(json.dumps({"id": None, "doc": doc})))
    assert reply["ok"], reply
    return reply["id"]


@pytest.fixture
def map_id(bundled: tuple[MapSpec, ...]) -> str:
    return bundled[0].id


def test_a_new_route_is_listed_last_whatever_its_name(backend: Backend, map_id: str) -> None:
    save_new(backend, map_id, "Moss")
    save_new(backend, map_id, "Zinc")
    last = save_new(backend, map_id, "Amber")

    assert listed(backend)[-1] == last


def test_a_route_already_on_disk_keeps_its_place_above_a_new_one(
    backend: Backend, dirs: DataDirs, map_id: str
) -> None:
    """An install from before the order existed: its routes are listed by name until the
    first new one, and that one goes under them, not between them."""
    for name in ("Beta", "Alpha"):
        routes.save_route(dirs, name, routes.new_route_doc(name, map_id, [512, 384]))
    new = save_new(backend, map_id, "Aardvark")

    assert listed(backend) == ["Alpha", "Beta", new]


def test_reorder_sets_the_order_and_survives_a_restart(
    qapp: QApplication, dirs: DataDirs, map_id: str
) -> None:
    first = Backend(dirs)
    try:
        a, b, c = (save_new(first, map_id, n) for n in ("One", "Two", "Three"))
        first.reorderRoutes(json.dumps([c, a, b]))
        assert listed(first) == [c, a, b]
    finally:
        first.shutdown()

    again = Backend(dirs)
    try:
        assert listed(again) == [c, a, b]
    finally:
        again.shutdown()


def test_reorder_cannot_lose_a_route_or_invent_one(backend: Backend, map_id: str) -> None:
    a, b, c = (save_new(backend, map_id, n) for n in ("One", "Two", "Three"))

    backend.reorderRoutes(json.dumps([b, "ghost", 7, b]))

    assert listed(backend) == [b, a, c]
    assert backend.state.route_order == [b]


def test_reorder_ignores_a_payload_that_is_not_a_list(backend: Backend, map_id: str) -> None:
    a, b = (save_new(backend, map_id, n) for n in ("One", "Two"))
    before = backend.state.route_order

    backend.reorderRoutes("{not json")
    backend.reorderRoutes(json.dumps({"order": [b, a]}))

    assert backend.state.route_order == before
    assert listed(backend) == [a, b]


def test_a_deleted_route_leaves_the_order(backend: Backend, map_id: str) -> None:
    a, b = (save_new(backend, map_id, n) for n in ("One", "Two"))

    backend.deleteRoute(a)

    assert backend.state.route_order == [b]
