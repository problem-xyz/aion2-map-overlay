"""routes/ changed behind the app: the panel and the open route follow without a restart."""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes
from map_overlay.store.maps import MapSpec

WAIT_MS = 5000


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def listed(backend: Backend) -> list[str]:
    return [r["id"] for r in json.loads(backend.getState())["routes"]]


def open_route(backend: Backend, dirs: DataDirs, spec: MapSpec) -> str:
    doc = routes.new_route_doc("Mine", spec.id, list(spec.size))
    doc["markers"] = [{"x": 1, "y": 2, "text": "A"}, {"x": 3, "y": 4, "text": "B"}]
    routes.save_route(dirs, "mine", doc)
    backend.setRoute("mine")
    return "mine"


def test_a_route_copied_into_the_folder_reaches_the_panel(
    backend: Backend, dirs: DataDirs, bundled: tuple[MapSpec, ...], qtbot: QtBot
) -> None:
    altgard = bundled[0]
    states: list[str] = []
    backend.stateChanged.connect(states.append)

    doc = routes.new_route_doc("Dropped", altgard.id, list(altgard.size))
    routes.route_path(dirs, "dropped").write_text(json.dumps(doc), encoding="utf-8")

    qtbot.waitUntil(lambda: any('"dropped"' in s for s in states), timeout=WAIT_MS)
    assert "dropped" in listed(backend)


def test_the_open_route_deleted_from_the_folder_is_closed_and_its_progress_kept(
    backend: Backend, dirs: DataDirs, bundled: tuple[MapSpec, ...], qtbot: QtBot
) -> None:
    route_id = open_route(backend, dirs, bundled[0])
    backend.setProgress(1)

    routes.route_path(dirs, route_id).unlink()

    qtbot.waitUntil(lambda: backend.route is None, timeout=WAIT_MS)
    assert backend._routes.active_doc is None
    assert backend.state.progress == {route_id: 1}


def test_the_open_route_edited_by_hand_is_redrawn(
    backend: Backend, dirs: DataDirs, bundled: tuple[MapSpec, ...], qtbot: QtBot
) -> None:
    route_id = open_route(backend, dirs, bundled[0])
    doc = routes.read_route_file(routes.route_path(dirs, route_id))
    doc["markers"].append({"x": 5, "y": 6, "text": "C"})

    routes.route_path(dirs, route_id).write_text(json.dumps(doc), encoding="utf-8")

    qtbot.waitUntil(
        lambda: len((backend._routes.active_doc or {}).get("markers", ())) == 3, timeout=WAIT_MS
    )
    assert backend.route == route_id


def test_the_open_route_edited_into_no_route_stays_open(
    backend: Backend, dirs: DataDirs, bundled: tuple[MapSpec, ...], qtbot: QtBot
) -> None:
    route_id = open_route(backend, dirs, bundled[0])
    before = backend._routes.active_doc
    states: list[str] = []
    backend.stateChanged.connect(states.append)

    routes.route_path(dirs, route_id).write_text('{"format": "not a route"}', encoding="utf-8")

    qtbot.waitUntil(lambda: bool(states), timeout=WAIT_MS)
    assert backend.route == route_id
    assert backend._routes.active_doc == before
