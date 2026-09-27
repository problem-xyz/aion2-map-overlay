"""A damaged file in routes/, the way the panel meets it: on every state rebuild.

The route list is rebuilt with the state -- on start, stop, each engine phase and every setting.
A damaged file there used to put a traceback in the log each of those times, while the route
vanished from the list without a notice and the file stayed where it was, unlike a damaged
settings.json, which is moved aside.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store.routes import new_route_doc, route_path, save_route

DAMAGED = '{"format": "map-overlay-route", "name": "cut off'


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def collect_notices(backend: Backend) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    backend.notify.connect(lambda payload: sent.append(json.loads(payload)))
    return sent


def test_a_damaged_route_file_is_reported_once_however_often_the_state_is_rebuilt(
    backend: Backend, dirs: DataDirs, caplog: pytest.LogCaptureFixture
) -> None:
    save_route(dirs, "good", new_route_doc("Good", "", [0, 0]))
    route_path(dirs, "broken").write_text(DAMAGED, encoding="utf-8")
    sent = collect_notices(backend)

    with caplog.at_level(logging.WARNING):
        state = json.loads(backend.getState())
        for _ in range(3):
            backend.refreshRoutes()
            backend.getState()

    assert [r["id"] for r in state["routes"]] == ["good"]
    assert [n["code"] for n in sent] == ["route.file_corrupt"]
    [notice] = sent
    assert notice["level"] == "warning"
    assert notice["params"]["file"] == "broken.json"
    assert (dirs.routes / notice["params"]["backup"]).read_text(encoding="utf-8") == DAMAGED
    assert not route_path(dirs, "broken").exists()
    assert not [r for r in caplog.records if r.exc_info], "a traceback on every rebuild"
    # One line each from the store, from the move and from the notice, for seven rebuilds.
    assert len([r for r in caplog.records if "broken.json" in r.getMessage()]) == 3


def test_a_notice_found_before_the_page_connects_waits_for_it(
    backend: Backend, dirs: DataDirs
) -> None:
    # A map finishing its tiles at start-up rebuilds the state before any page has asked for
    # it, and the notice comes up only once, so sending it into the void would lose it.
    route_path(dirs, "broken").write_text("", encoding="utf-8")
    sent = collect_notices(backend)

    backend.refreshRoutes()
    assert sent == []

    backend.getState()
    assert [n["code"] for n in sent] == ["route.file_corrupt"]
