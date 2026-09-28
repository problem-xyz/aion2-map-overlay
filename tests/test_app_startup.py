"""main() as a second launch meets it: the lock is already held.

A second launch used to write a full start-up header into the running copy's log and run
migrate_dev_layout -- which moves whole directories -- before it looked at the lock, so two
processes could migrate the same data at once. It also asked the running copy to come forward
without handing it the right to, so the copy's window could only flash on the taskbar.

It also gave up on a copy that had taken the lock but was still building its windows: one try,
no answer, and it started beside it. A double-click on the shortcut lands exactly there.

Every collaborator that could touch the repository or open a window is replaced: app_root() is
the checkout itself here, and a real migration would move its data into the test directory.
"""

import functools
import logging
import os
import subprocess
import sys
import threading
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import qInstallMessageHandler, qWarning
from PySide6.QtWidgets import QApplication

import map_overlay
from map_overlay import __version__
from map_overlay import app as app_module
from map_overlay.core.appinfo import APP_NAME
from map_overlay.core.logs import LOG_NAME
from map_overlay.core.paths import DataDirs
from map_overlay.core.single_instance import CONNECT_TIMEOUT_MS, Answer, SingleInstance

HEADER = f"{APP_NAME} {__version__} starting"
SRC = Path(map_overlay.__file__).parents[1]

# The first copy as a double-click's second launch finds it, in a process of its own. It holds
# the lock while it builds its windows and listens only after that; the pause after listen() is
# the rest of main() before app.exec(), when a request can reach the pipe but nothing reads it.
# That pause is longer than the second launch used to wait for its request to be read.
STARTING_COPY = """
import os, sys, time
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QTimer
from map_overlay.core.paths import DataDirs
from map_overlay.core.single_instance import SingleInstance

root, name = Path(sys.argv[1]), sys.argv[2]
building, before_exec = float(sys.argv[3]), float(sys.argv[4])
instance = SingleInstance(DataDirs.from_root(root), server_name=name)
if not instance.try_acquire():
    sys.exit("the lock was already taken")
app = QCoreApplication([])
print("locked", os.getpid(), flush=True)
time.sleep(building)
asked = []
instance.listen(lambda: (asked.append(True), app.quit()))
time.sleep(before_exec)
QTimer.singleShot(5000, app.quit)
app.exec()
instance.release()
sys.exit(0 if asked else 3)
"""
# Long enough for main() to reach the wait while the copy is still building, try_acquire's own
# timeout included, on a slow runner too.
BUILDING_S = 0.8
BEFORE_EXEC_S = CONNECT_TIMEOUT_MS / 1000 + 0.2


class _WouldStartError(Exception):
    """Raised where a real start would build the Backend and its windows."""


class _FakeQApplication:
    """main() builds a QApplication, and the test session already has the one Qt allows."""

    def __init__(self, argv: list[str]) -> None:
        pass

    @staticmethod
    def setAttribute(attribute: Any, on: bool = True) -> None:  # noqa: N802 -- Qt's name
        pass

    def setApplicationName(self, name: str) -> None:  # noqa: N802 -- Qt's name
        pass


@pytest.fixture
def process_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """main() sets up logging for the whole process; put back what pytest had."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    try:
        yield
    finally:
        for handler in list(root.handlers):
            if handler not in handlers:
                root.removeHandler(handler)
                handler.close()
        for handler in handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(level)
        qInstallMessageHandler(None)


@pytest.fixture
def running_copy(qapp: QApplication, tmp_path: Path) -> Iterator[DataDirs]:
    """A data directory whose lock another instance -- this test -- already holds."""
    dirs = DataDirs.from_root(tmp_path / "data")
    dirs.root.mkdir()
    holder = SingleInstance(dirs)
    assert holder.try_acquire()
    try:
        yield dirs
    finally:
        holder.release()


@pytest.fixture
def starting_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[DataDirs, subprocess.Popen[str], int]]:
    """A data directory whose lock a first copy, still starting, holds in another process.

    Also yields that process's pid, which is not the child's: a venv's python.exe on Windows is
    a launcher that runs the real interpreter as a process of its own.
    """
    dirs = DataDirs.from_root(tmp_path / "data")
    dirs.root.mkdir()
    # A socket name of its own, so that nothing here reaches a copy of the app left open.
    name = f"map-overlay-test-{uuid.uuid4().hex}"
    monkeypatch.setattr(
        app_module, "SingleInstance", functools.partial(SingleInstance, server_name=name)
    )
    timings = (str(BUILDING_S), str(BEFORE_EXEC_S))
    child = subprocess.Popen(
        [sys.executable, "-c", STARTING_COPY, str(dirs.root), name, *timings],
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(SRC)},
    )
    try:
        assert child.stdout is not None
        word, pid = child.stdout.readline().split()
        assert word == "locked"
        yield dirs, child, int(pid)
    finally:
        child.kill()
        child.wait()


def stub_start(monkeypatch: pytest.MonkeyPatch, dirs: DataDirs) -> list[Any]:
    """Point main() at dirs with nothing real behind it, and record what it did, in order."""
    made: list[Any] = []

    def migrate(root: Path, dirs: DataDirs) -> list[str]:
        made.append("migrate")
        return []

    def grant(pid: int | None) -> bool:
        made.append(("grant", pid))
        return True

    def backend(*args: Any, **kwargs: Any) -> None:
        raise _WouldStartError

    monkeypatch.setattr(sys, "argv", ["map-overlay", "--data-dir", str(dirs.root)])
    monkeypatch.setattr(app_module, "migrate_dev_layout", migrate)
    monkeypatch.setattr(app_module, "QApplication", _FakeQApplication)
    monkeypatch.setattr(app_module, "Backend", backend)
    # The real one would turn automatic collection off for the rest of the session.
    monkeypatch.setattr(app_module, "GuiCollector", lambda app: None)
    # The real choice is made once per process and sticks: this one serves the whole session
    monkeypatch.setattr(app_module, "choose_graphics_api", lambda **_: "stub")
    monkeypatch.setattr("map_overlay.qt.win32.allow_set_foreground", grant, raising=False)
    return made


@pytest.fixture
def calls(
    running_copy: DataDirs, monkeypatch: pytest.MonkeyPatch, process_logging: None
) -> list[Any]:
    """What main() did, in order, with nothing real behind it."""
    return stub_start(monkeypatch, running_copy)


def answer(monkeypatch: pytest.MonkeyPatch, calls: list[Any], reply: Answer) -> None:
    def signal(self: SingleInstance, wait_ms: int = 0) -> Answer:
        calls.append("signal")
        return reply

    monkeypatch.setattr(SingleInstance, "signal_existing", signal)


def log_of(dirs: DataDirs) -> str:
    return (dirs.logs / LOG_NAME).read_text(encoding="utf-8")


def test_a_second_launch_leaves_before_it_touches_the_data(
    running_copy: DataDirs, calls: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    answer(monkeypatch, calls, Answer.RAISED)

    assert app_module.main() == 0

    assert "migrate" not in calls
    assert not running_copy.maps.exists()
    assert not running_copy.routes.exists()
    text = log_of(running_copy)
    assert "another instance is already running; raised it and exiting" in text
    assert HEADER not in text, "the running copy's log would read as if it had restarted"


def test_a_second_launch_hands_the_foreground_over_before_it_asks(
    running_copy: DataDirs, calls: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    answer(monkeypatch, calls, Answer.RAISED)

    app_module.main()

    assert calls == [("grant", os.getpid()), "signal"]


def test_a_launch_nobody_answers_starts_anyway_with_a_header_of_its_own(
    running_copy: DataDirs, calls: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    answer(monkeypatch, calls, Answer.SILENT)

    with pytest.raises(_WouldStartError):
        app_module.main()

    assert calls == [("grant", os.getpid()), "signal", "migrate"]
    text = log_of(running_copy)
    assert text.index(HEADER) < text.index("the lock is held but nobody answered")


@pytest.mark.no_qt_log
def test_qt_messages_join_the_log_only_once_the_wait_is_over(
    running_copy: DataDirs, calls: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Routed any earlier, they hung the launch: see core.logs.route_qt_messages."""

    def signal(self: SingleInstance, wait_ms: int = 0) -> Answer:
        qWarning("said during the wait")
        return Answer.TOOK_OVER

    monkeypatch.setattr(SingleInstance, "signal_existing", signal)

    with pytest.raises(_WouldStartError):
        app_module.main()
    qWarning("said once it has started")

    text = log_of(running_copy)
    assert "said during the wait" not in text
    assert "said once it has started" in text


def test_a_launch_that_outlives_the_copy_it_waited_for_starts_in_its_place(
    running_copy: DataDirs, calls: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    answer(monkeypatch, calls, Answer.TOOK_OVER)

    with pytest.raises(_WouldStartError):
        app_module.main()

    assert calls == [("grant", os.getpid()), "signal", "migrate"]
    text = log_of(running_copy)
    assert HEADER in text
    assert "nobody answered" not in text, "it holds the lock, so it is not a second copy"


@pytest.mark.no_qt_log  # pytest-qt's Python handler is what route_qt_messages() waits out
def test_a_launch_that_races_a_starting_copy_raises_it_instead_of_starting_beside_it(
    starting_copy: tuple[DataDirs, subprocess.Popen[str], int],
    monkeypatch: pytest.MonkeyPatch,
    process_logging: None,
) -> None:
    dirs, first, pid = starting_copy
    calls = stub_start(monkeypatch, dirs)

    assert app_module.main() == 0

    assert first.wait(timeout=10) == 0, "the first copy never read the request"
    assert calls == [("grant", pid)]
    text = log_of(dirs)
    assert "has not answered yet; waiting" in text
    assert "another instance is already running; raised it and exiting" in text
    assert HEADER not in text
