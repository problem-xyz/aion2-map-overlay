"""The saved map area and plaque position against the monitors there are now, through Backend.

The monitors are faked at the two functions Backend reads them through, so a layout with a
second monitor -- and its removal -- can be played on a CI machine that has one offscreen
screen. The geometry itself is pinned in tests/core/test_geometry.py; this file pins what the
app does about it: the notice, the cleared state, and an engine that is stopped or never started
rather than left capturing a rectangle that is not there.
"""

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge import backend as backend_module
from map_overlay.bridge.backend import Backend
from map_overlay.bridge.engine_controller import Phase
from map_overlay.core.geometry import Rect
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Region, State, state_payload
from map_overlay.qt.screens import ScreenWatcher

PRIMARY: Rect = (0, 0, 1920, 1080)
RIGHT: Rect = (1920, 0, 1920, 1080)
ON_RIGHT = Region(left=2500, top=300, width=800, height=600)
ON_PRIMARY = Region(left=100, top=100, width=800, height=600)


class Layout:
    """The monitors the fake reports; a test edits `screens` to plug or unplug one."""

    def __init__(self) -> None:
        self.screens: list[Rect] = [PRIMARY, RIGHT]


@pytest.fixture
def layout(monkeypatch: pytest.MonkeyPatch) -> Layout:
    made = Layout()
    monkeypatch.setattr(backend_module, "screen_rects", lambda: list(made.screens))
    monkeypatch.setattr(backend_module, "primary_rect", lambda: PRIMARY)
    monkeypatch.setattr(backend_module, "windows_version", lambda: (10, 0, 26100))
    return made


@pytest.fixture
def make_backend(
    qapp: QApplication, dirs: DataDirs, layout: Layout
) -> Iterator[Callable[[], Backend]]:
    made: list[Backend] = []

    def build() -> Backend:
        backend = Backend(dirs)
        made.append(backend)
        return backend

    yield build
    for backend in made:
        backend.shutdown()


def save_state(dirs: DataDirs, **fields: Any) -> None:
    dirs.state.write_text(json.dumps(state_payload(State(**fields))), encoding="utf-8")


def listen(backend: Backend) -> list[dict[str, Any]]:
    notices: list[dict[str, Any]] = []
    backend.notify.connect(lambda raw: notices.append(json.loads(raw)))
    return notices


def codes(notices: list[dict[str, Any]]) -> list[str]:
    return [n["code"] for n in notices]


# --------------------------------------------------------------------------- at start-up


def test_a_map_area_on_a_monitor_unplugged_between_runs_is_cleared_with_a_notice(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    save_state(dirs, region=ON_RIGHT)
    layout.screens = [PRIMARY]

    backend = make_backend()
    notices = listen(backend)
    state = json.loads(backend.getState())  # the first getState drains start-up notices

    assert backend.state.region is None
    assert state["region"] is None
    assert codes(notices) == ["region.offscreen"]
    assert notices[0]["level"] == "warning"
    # The position as text, so the UI does not group it into "at 1,920, 0"; the size stays a
    # number.
    assert notices[0]["params"] == dict(
        ON_RIGHT, left=str(ON_RIGHT["left"]), top=str(ON_RIGHT["top"])
    )
    backend._store.flush()
    assert json.loads(dirs.state.read_text(encoding="utf-8"))["region"] is None


def test_a_map_area_on_a_monitor_that_is_still_there_is_kept(
    make_backend: Callable[[], Backend], dirs: DataDirs
) -> None:
    save_state(dirs, region=ON_RIGHT)

    backend = make_backend()
    notices = listen(backend)
    backend.getState()

    assert backend.state.region == ON_RIGHT
    assert "region.offscreen" not in codes(notices)


def test_a_plaque_left_on_an_unplugged_monitor_is_moved_back_without_a_notice(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    save_state(dirs, steps_region=Region(left=2500, top=300, width=430, height=160))
    layout.screens = [PRIMARY]

    backend = make_backend()
    notices = listen(backend)
    backend.getState()

    assert backend.state.steps_region == Region(left=1490, top=300, width=430, height=160)
    assert notices == []


# --------------------------------------------------------------------------- monitor changes


def test_unplugging_the_monitor_with_the_map_area_clears_it_and_says_so(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    save_state(dirs, region=ON_RIGHT)
    backend = make_backend()
    backend.getState()  # the page is up
    notices = listen(backend)
    states: list[str] = []
    backend.stateChanged.connect(states.append)

    layout.screens = [PRIMARY]
    backend._screens.changed.emit()

    assert backend.state.region is None
    assert codes(notices) == ["region.offscreen"]
    assert states, "the panel has to stop showing the old area"
    assert json.loads(states[-1])["region"] is None


def test_a_monitor_change_before_the_page_connects_keeps_its_notice_for_it(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    """The watcher fires a second after the layout settles, and a cold QtWebEngine can take
    longer than that to load the page. Emitted then, the notice reached nobody, and the user
    found the map area gone without a word."""
    save_state(dirs, region=ON_RIGHT)
    backend = make_backend()
    notices = listen(backend)

    layout.screens = [PRIMARY]
    backend._screens.changed.emit()
    assert backend.state.region is None
    assert notices == []  # no page yet: QWebChannel would have dropped it

    backend.getState()
    assert codes(notices) == ["region.offscreen"]
    backend.getState()
    assert codes(notices) == ["region.offscreen"]  # delivered once


def test_unplugging_it_while_running_stops_the_engine_before_it_captures_nothing(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    """Under dxcam every grab of a rectangle off the output raises; under mss it is black."""
    save_state(dirs, region=ON_RIGHT)
    backend = make_backend()
    backend.engine._set_phase(Phase.RUNNING)  # as if start() had been confirmed by the thread
    backend.getState()
    notices = listen(backend)

    layout.screens = [PRIMARY]
    backend._screens.changed.emit()

    assert backend.engine.phase is Phase.STOPPING
    assert backend.engine._engine._stop.is_set()
    assert backend.state.region is None
    assert codes(notices) == ["region.offscreen"]


def test_a_monitor_change_that_leaves_everything_visible_changes_nothing(
    make_backend: Callable[[], Backend], dirs: DataDirs, layout: Layout
) -> None:
    save_state(dirs, region=ON_PRIMARY)
    backend = make_backend()
    notices = listen(backend)
    states: list[str] = []
    backend.stateChanged.connect(states.append)

    layout.screens = [PRIMARY]
    backend._screens.changed.emit()

    assert backend.state.region == ON_PRIMARY
    assert notices == []
    assert states == []


def test_start_refuses_a_map_area_that_went_before_the_watcher_noticed(
    make_backend: Callable[[], Backend],
    dirs: DataDirs,
    layout: Layout,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The watcher waits for the layout to settle; a Start pressed inside that second must not
    hand the engine a rectangle that is on no screen."""
    save_state(dirs, region=ON_RIGHT)
    backend = make_backend()
    started: list[dict[str, Any]] = []
    monkeypatch.setattr(backend.engine, "start", lambda **kw: started.append(kw))
    backend.getState()
    notices = listen(backend)

    layout.screens = [PRIMARY]
    backend.start()

    assert started == []
    assert backend.engine.phase is Phase.IDLE
    assert backend.state.region is None
    # One notice that says what happened, not a second one asking for an area as well.
    assert codes(notices) == ["region.offscreen"]


# --------------------------------------------------------------------------- the watcher


def test_the_watcher_turns_a_burst_of_screen_signals_into_one_change(qapp: QApplication) -> None:
    watcher = ScreenWatcher(settle_ms=50)
    fired: list[bool] = []
    watcher.changed.connect(lambda: fired.append(True))
    screen = QGuiApplication.primaryScreen()

    for _ in range(3):
        screen.geometryChanged.emit(screen.geometry())
    qapp.primaryScreenChanged.emit(screen)
    QTest.qWait(200)

    assert fired == [True]
    watcher.close()


def test_a_closed_watcher_ignores_the_screens(qapp: QApplication) -> None:
    """The application's signals outlive a shut-down Backend; its watcher must fall silent."""
    watcher = ScreenWatcher(settle_ms=20)
    fired: list[bool] = []
    watcher.changed.connect(lambda: fired.append(True))
    watcher.close()

    screen = QGuiApplication.primaryScreen()
    screen.geometryChanged.emit(screen.geometry())
    QTest.qWait(100)

    assert fired == []
