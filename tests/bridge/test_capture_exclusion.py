"""What Backend does with a Windows too old to hide a window from capture.

Before 10.0.19041 Windows treats WDA_EXCLUDEFROMCAPTURE as WDA_MONITOR, which paints the window
black in every capture -- the engine's own frames included. So on such a system the overlay and
the plaque are kept capturable whatever the setting says, the user is told once, and getState
says so for the panel to grey the option out. The version itself is faked at the one function
Backend reads it through.
"""

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge import backend as backend_module
from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs

Version = tuple[int, int, int] | None


@pytest.fixture
def make_backend(
    qapp: QApplication, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[Version], Backend]]:
    made: list[Backend] = []

    def build(version: Version) -> Backend:
        monkeypatch.setattr(backend_module, "windows_version", lambda: version)
        backend = Backend(dirs)
        made.append(backend)
        return backend

    yield build
    for backend in made:
        backend.shutdown()


def first_state(backend: Backend) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    notices: list[dict[str, Any]] = []
    backend.notify.connect(lambda raw: notices.append(json.loads(raw)))
    return json.loads(backend.getState()), notices


def test_windows_1909_gets_a_warning_and_a_capturable_overlay(
    make_backend: Callable[[Version], Backend],
) -> None:
    backend = make_backend((10, 0, 18363))

    state, notices = first_state(backend)

    assert state["captureExclusion"] is False
    assert state["captureVisible"] is False  # the setting is untouched; the windows ignore it
    assert [(n["level"], n["code"]) for n in notices] == [("warning", "system.old_windows")]
    assert notices[0]["params"] == {"version": "10.0.18363"}
    assert backend.overlay._recordable is True
    assert backend.steps._recordable is True


def test_the_warning_is_given_once_not_on_every_state(
    make_backend: Callable[[Version], Backend],
) -> None:
    backend = make_backend((10, 0, 18363))
    _, notices = first_state(backend)

    backend.getState()
    backend.getState()

    assert [n["code"] for n in notices] == ["system.old_windows"]


def test_turning_recording_visibility_off_cannot_hide_the_overlay_there(
    make_backend: Callable[[Version], Backend],
) -> None:
    backend = make_backend((10, 0, 18363))

    backend.setCaptureVisible(True)
    backend.setCaptureVisible(False)
    backend.resetSettings()

    assert backend.overlay._recordable is True
    assert backend.steps._recordable is True


@pytest.mark.parametrize("version", [(10, 0, 19041), (10, 0, 26100), None])
def test_windows_2004_and_later_or_an_unknown_one_hide_the_overlay_quietly(
    make_backend: Callable[[Version], Backend], version: Version
) -> None:
    backend = make_backend(version)

    state, notices = first_state(backend)

    assert state["captureExclusion"] is True
    assert notices == []
    assert backend.overlay._recordable is False
    assert backend.steps._recordable is False
