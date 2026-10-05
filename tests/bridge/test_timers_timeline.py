"""The day timeline's window through Backend: built on first use, one only, and back where it was
left the next time."""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def test_the_timeline_opens_once_and_closes(backend: Backend) -> None:
    assert not backend._windows.timeline_visible()
    backend.openTimersTimeline()
    first = backend._windows._timeline
    assert first is not None and first.isVisible()
    backend.openTimersTimeline()
    assert backend._windows._timeline is first, "a second open raises the same window"
    backend.closeTimersTimeline()
    assert not backend._windows.timeline_visible()


def test_the_timeline_remembers_where_it_was_left(backend: Backend) -> None:
    backend.openTimersTimeline()
    window = backend._windows._timeline
    assert window is not None
    window.setGeometry(40, 60, 1500, 820)
    window.close()  # the title bar's cross hides it
    assert not window.isVisible()
    assert backend.state.timers_timeline_region == {
        "left": 40,
        "top": 60,
        "width": 1500,
        "height": 820,
    }


def test_a_region_off_every_screen_is_not_used(backend: Backend) -> None:
    far = {"left": 90_000, "top": 90_000, "width": 900, "height": 420}
    backend._store.set_state(timers_timeline_region=far)
    backend.openTimersTimeline()
    window = backend._windows._timeline
    assert window is not None
    assert window.geometry().x() != far["left"]
