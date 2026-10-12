"""The pets' map window through Backend: built on first use, one only, the size of the editor and
back where it was left the next time."""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.i18n.catalog import t


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def test_the_map_opens_once_and_closes(backend: Backend) -> None:
    assert not backend._windows.pets_map_visible()
    backend.openPetsMap()
    first = backend._windows._pets_map
    assert first is not None and first.isVisible()
    assert first.windowTitle() == t("native.window.petsMap")
    assert first.view.url().fragment() == "pets-map"
    backend.openPetsMap()
    assert backend._windows._pets_map is first, "a second open raises the same window"
    backend.closePetsMap()
    assert not backend._windows.pets_map_visible()


def test_the_map_is_its_own_window_beside_the_timeline(backend: Backend) -> None:
    backend.openPetsMap()
    backend.openTimersTimeline()

    assert backend._windows._pets_map is not backend._windows._timeline
    assert backend._windows.pets_map_visible()
    assert backend._windows.timeline_visible()


def test_the_map_remembers_where_it_was_left(backend: Backend) -> None:
    backend.openPetsMap()
    window = backend._windows._pets_map
    assert window is not None
    window.setGeometry(40, 60, 1400, 900)
    window.close()  # the title bar's cross hides it
    assert not window.isVisible()
    assert backend.state.pets_map_region == {"left": 40, "top": 60, "width": 1400, "height": 900}
