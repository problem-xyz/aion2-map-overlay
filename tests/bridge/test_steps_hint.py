"""The drag hint that comes with the steps list, shown once per machine.

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
