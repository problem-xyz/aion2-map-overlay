"""The steps list, on for a new install, and the drag hint that comes with it once per machine.

The hint was always meant for "the first time you show the list", while the slot sent the
notice on every switch. The fact that it was shown now lives in state.json, so a restart does
not bring it back either.
"""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes
from map_overlay.store.maps import MapSpec

HINT = "steps.drag_hint"


def hints_while(backend: Backend, *switches: bool) -> int:
    codes: list[str] = []
    backend.notify.connect(lambda raw: codes.append(json.loads(raw)["code"]))
    for visible in switches:
        backend.setStepsVisible(visible)
    return codes.count(HINT)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def test_the_hint_comes_with_the_first_switch_on_and_not_the_next(backend: Backend) -> None:
    assert hints_while(backend, True, False, True, False, True) == 1


def test_switching_the_list_off_is_not_the_first_time(backend: Backend) -> None:
    assert hints_while(backend, False) == 0
    assert hints_while(backend, True) == 1


def test_a_restart_does_not_bring_the_hint_back(qapp: QApplication, dirs: DataDirs) -> None:
    first = Backend(dirs)
    try:
        assert hints_while(first, True) == 1
    finally:
        first.shutdown()  # flushes state.json
    assert json.loads(dirs.state.read_text(encoding="utf-8"))["steps_hint_shown"] is True

    second = Backend(dirs)
    try:
        assert hints_while(second, False, True) == 0
    finally:
        second.shutdown()


def test_a_new_install_starts_with_the_list_on(backend: Backend) -> None:
    assert json.loads(backend.getState())["steps"]["visible"] is True


def test_a_list_turned_off_stays_off_after_a_restart(qapp: QApplication, dirs: DataDirs) -> None:
    first = Backend(dirs)
    try:
        first.setStepsVisible(False)
    finally:
        first.shutdown()

    second = Backend(dirs)
    try:
        assert json.loads(second.getState())["steps"]["visible"] is False
    finally:
        second.shutdown()


def test_with_the_list_on_from_the_start_the_hint_comes_when_it_first_shows(
    backend: Backend, dirs: DataDirs, bundled: tuple[MapSpec, ...]
) -> None:
    spec = bundled[0]
    doc = routes.new_route_doc("Steps", spec.id, list(spec.size))
    doc["markers"] = [{"x": 1, "y": 2, "text": "Talk to the elder"}]
    routes.save_route(dirs, "steps", doc)
    codes: list[str] = []
    backend.notify.connect(lambda raw: codes.append(json.loads(raw)["code"]))
    backend.getState()  # the page connects

    backend.setRoute("steps")
    backend.setRoute("steps")

    assert codes.count(HINT) == 1
    assert hints_while(backend, False, True) == 0
