"""The checklist is moved by its body and sized by its right and bottom edges, by the mouse.

Both gestures used to end when GetAsyncKeyState said the button was up, and Windows says "up"
whenever an elevated window -- the game -- is in front: the plaque could only be dragged while the
panel was. They end on Qt's own release now, which these tests feed to the window's filter as
the QWindow would. The zoom scales the size the user left, rather than setting a width of its own.
"""

import json
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Region, plaque_scale
from map_overlay.qt.steps_window import WebStepsWindow, scale_region

LEFT = Qt.MouseButton.LeftButton
NONE = Qt.MouseButton.NoButton


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def mouse(
    window: WebStepsWindow,
    kind: QEvent.Type,
    x: int,
    y: int,
    *,
    button: Qt.MouseButton = NONE,
    held: bool = False,
) -> bool:
    """One mouse event at a window-local point, through the window's filter; True if taken."""
    local = QPointF(x, y)
    screen = QPointF(window.mapToGlobal(QPoint(x, y)))
    event = QMouseEvent(
        kind, local, screen, button, LEFT if held else NONE, Qt.KeyboardModifier.NoModifier
    )
    return window.eventFilter(window, event)


def loose(backend: Backend, region: Region) -> WebStepsWindow:
    window = backend.steps
    window.set_pinned(False)
    window.set_region(region)
    return window


def moves(window: WebStepsWindow) -> list[dict[str, int]]:
    seen: list[dict[str, int]] = []
    window.regionChanged.connect(seen.append)
    return seen


def test_the_zoom_scales_a_region_from_its_corner() -> None:
    region: Region = {"left": 10, "top": 20, "width": 400, "height": 300}
    assert scale_region(region, 1.5) == {"left": 10, "top": 20, "width": 600, "height": 450}


def test_the_strips_along_the_right_and_bottom_edges(backend: Backend) -> None:
    window = loose(backend, {"left": 0, "top": 0, "width": 400, "height": 300})
    g = window.GRIP
    assert window.edges_at(QPoint(399, 150)) == "r"
    assert window.edges_at(QPoint(200, 299)) == "b"
    assert window.edges_at(QPoint(400 - 2 * g, 300 - 2 * g)) == "rb"
    assert window.edges_at(QPoint(400 - g - 1, 150)) == ""
    assert window.edges_at(QPoint(10, 10)) == ""


def test_a_press_on_the_right_edge_sizes_the_plaque_and_never_reaches_the_page(
    backend: Backend,
) -> None:
    window = loose(backend, {"left": 0, "top": 0, "width": 400, "height": 300})
    seen = moves(window)

    assert mouse(window, QEvent.Type.MouseButtonPress, 398, 100, button=LEFT, held=True)
    assert mouse(window, QEvent.Type.MouseMove, 448, 140, held=True)
    assert (window.width(), window.height()) == (450, 300)  # the right edge moves width alone
    assert seen == []  # persisted once, when the user lets go
    assert mouse(window, QEvent.Type.MouseButtonRelease, 448, 140, button=LEFT)

    assert [(r["width"], r["height"]) for r in seen] == [(450, 300)]


def test_the_corner_sizes_both_ways_and_stops_at_the_least_there_is(backend: Backend) -> None:
    window = loose(backend, {"left": 0, "top": 0, "width": 400, "height": 300})

    mouse(window, QEvent.Type.MouseButtonPress, 398, 298, button=LEFT, held=True)
    mouse(window, QEvent.Type.MouseMove, 418, 318, held=True)
    assert (window.width(), window.height()) == (420, 320)
    mouse(window, QEvent.Type.MouseMove, 0, 0, held=True)
    scale = window._scale
    assert (window.width(), window.height()) == (
        round(WebStepsWindow.MIN_WIDTH * scale),
        round(WebStepsWindow.MIN_HEIGHT * scale),
    )


def test_a_pinned_plaque_is_not_sized(backend: Backend) -> None:
    window = loose(backend, {"left": 0, "top": 0, "width": 400, "height": 300})
    window.set_pinned(True)

    assert not mouse(window, QEvent.Type.MouseButtonPress, 398, 100, button=LEFT, held=True)
    assert not mouse(window, QEvent.Type.MouseMove, 448, 100, held=True)
    assert window.width() == 400


def test_a_drag_follows_the_mouse_and_ends_on_qts_release(backend: Backend) -> None:
    window = loose(backend, {"left": 100, "top": 100, "width": 400, "height": 300})
    seen = moves(window)

    # the page gets the press on the body, and says so; the window moves on the events it sees
    assert not mouse(window, QEvent.Type.MouseButtonPress, 50, 20, button=LEFT, held=True)
    window.begin_drag()
    mouse(window, QEvent.Type.MouseMove, 80, 60, held=True)
    assert (window.x(), window.y()) == (130, 140)
    mouse(window, QEvent.Type.MouseButtonRelease, 50, 20, button=LEFT)

    assert [(r["left"], r["top"]) for r in seen] == [(130, 140)]


def test_a_drag_whose_release_went_astray_ends_on_the_next_move(backend: Backend) -> None:
    window = loose(backend, {"left": 100, "top": 100, "width": 400, "height": 300})
    seen = moves(window)

    mouse(window, QEvent.Type.MouseButtonPress, 50, 20, button=LEFT, held=True)
    window.begin_drag()
    mouse(window, QEvent.Type.MouseMove, 70, 20)  # the button is up

    assert len(seen) == 1
    mouse(window, QEvent.Type.MouseMove, 200, 200)
    assert (window.x(), window.y()) == (100, 100)


def test_the_stored_region_does_not_pull_a_plaque_back_mid_gesture(backend: Backend) -> None:
    window = loose(backend, {"left": 0, "top": 0, "width": 400, "height": 300})

    mouse(window, QEvent.Type.MouseButtonPress, 398, 100, button=LEFT, held=True)
    mouse(window, QEvent.Type.MouseMove, 448, 100, held=True)
    window.set_region({"left": 0, "top": 0, "width": 400, "height": 300})  # a progress tick

    assert window.width() == 450


def test_the_zoom_takes_the_size_the_user_left_with_it(backend: Backend) -> None:
    backend.updateSettings(json.dumps({"steps_scale": 0.5}))
    backend._store.set_state(steps_region={"left": 5, "top": 6, "width": 300, "height": 200})

    backend.updateSettings(json.dumps({"steps_scale": 1.5}))

    ratio = plaque_scale(1.5) / plaque_scale(0.5)
    assert backend.state.steps_region == {
        "left": 5,
        "top": 6,
        "width": round(300 * ratio),
        "height": round(200 * ratio),
    }


def test_a_plaque_never_placed_starts_at_the_zoom_set(backend: Backend) -> None:
    window = backend.steps
    region = window.default_region()
    assert (region["width"], region["height"]) == (
        round(WebStepsWindow.BASE_WIDTH * window._scale),
        round(WebStepsWindow.BASE_HEIGHT * window._scale),
    )
    assert json.loads(window.data_json())["grip"] == WebStepsWindow.GRIP
