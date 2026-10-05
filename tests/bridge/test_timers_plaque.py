"""The timers plaque through Backend: built only when first shown, its buttons turned into
settings and state, folding to its head and back, and a peek when the sound is off."""

import json
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.qt.timers_window import TimersPlaqueWindow


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def plaque_window(backend: Backend) -> TimersPlaqueWindow:
    window = backend._timers_plaque.window
    assert window is not None
    return window


def data(backend: Backend) -> dict[str, Any]:
    return json.loads(plaque_window(backend).data_json())


def test_the_plaque_is_not_built_until_it_is_shown(backend: Backend) -> None:
    assert backend._timers_plaque.window is None
    assert json.loads(backend.getState())["timersPlaque"] == {"visible": False, "pinned": True}
    backend.setTimersPlaqueVisible(True)
    assert plaque_window(backend).isVisible()
    assert backend.state.timers_plaque_visible
    assert data(backend)["timers"]["events"], "it gets the timers the panel has"


def test_its_buttons_become_settings(backend: Backend) -> None:
    backend.setTimersPlaqueVisible(True)
    window = plaque_window(backend)
    window.actionClicked.emit("filter:boss")
    window.actionClicked.emit("pin")
    assert backend.settings.timers_plaque_filter == "boss"
    assert backend.settings.timers_plaque_pinned is False
    assert data(backend)["filter"] == "boss" and data(backend)["pinned"] is False
    window.actionClicked.emit("close")
    assert not window.isVisible() and not backend.state.timers_plaque_visible


def test_folding_keeps_the_height_to_unfold_to(backend: Backend) -> None:
    backend.setTimersPlaqueVisible(True)
    window = plaque_window(backend)
    window.set_region({"left": 100, "top": 100, "width": 330, "height": 300})
    plaque_window(backend).actionClicked.emit("collapse")
    assert backend.settings.timers_plaque_collapsed
    assert window.height() == TimersPlaqueWindow.COLLAPSED_HEIGHT
    assert window.region_dict()["height"] == 300
    window.actionClicked.emit("collapse")
    assert window.height() == 300


def test_a_moved_plaque_is_kept_in_state(backend: Backend) -> None:
    backend.setTimersPlaqueVisible(True)
    region = {"left": 40, "top": 50, "width": 320, "height": 280}
    plaque_window(backend).regionChanged.emit(region)
    assert backend.state.timers_plaque_region == region


def test_with_the_sound_off_a_reminder_peeks_and_goes(backend: Backend) -> None:
    backend._timers_plaque.peek()
    window = plaque_window(backend)
    assert window.isVisible() and window.peeking
    assert not backend.state.timers_plaque_visible, "a peek is not the user putting it up"
    window._end_peek()
    assert not window.isVisible()


def test_a_reminder_marks_its_row(backend: Backend) -> None:
    backend.setTimersPlaqueVisible(True)
    backend._timers.reminded.emit(json.dumps({"id": "rift", "name": "Spacetime Rift", "start": 1}))
    assert data(backend)["ring"]["id"] == "rift"
