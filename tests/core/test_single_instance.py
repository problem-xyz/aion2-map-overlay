"""SingleInstance: who a second launch hands the foreground to, and how long it waits for them.

Every instance a test asks to signal gets a socket name of its own, so that nothing here can
reach a copy of the app left open on the machine that runs the tests.
"""

import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

import map_overlay
from map_overlay.core.paths import DataDirs
from map_overlay.core.single_instance import Answer, SingleInstance

# pytest-qt catches Qt's messages with a Python handler, which signal_existing must not run
# under (see core.logs.route_qt_messages): with it, a copy that hangs up hangs the test.
pytestmark = pytest.mark.no_qt_log

# A copy on its way out, in a process of its own: it is listening, but its event loop is over,
# so nothing reads a request before it closes the socket and gives up the lock.
QUITTING_COPY = """
import sys, time
from pathlib import Path
from PySide6.QtCore import QCoreApplication
from map_overlay.core.paths import DataDirs
from map_overlay.core.single_instance import SingleInstance

instance = SingleInstance(DataDirs.from_root(Path(sys.argv[1])), server_name=sys.argv[2])
if not instance.try_acquire():
    sys.exit("the lock was already taken")
app = QCoreApplication([])
instance.listen(lambda: None)
print("listening", flush=True)
time.sleep(float(sys.argv[3]))
instance.release()
"""


def nobody_listens() -> str:
    return f"map-overlay-test-{uuid.uuid4().hex}"


def test_owner_pid_names_the_process_that_holds_the_lock(dirs: DataDirs) -> None:
    running = SingleInstance(dirs)
    assert running.try_acquire()
    try:
        assert SingleInstance(dirs).owner_pid() == os.getpid()
    finally:
        running.release()


def test_owner_pid_is_none_when_nobody_holds_the_lock(dirs: DataDirs) -> None:
    assert SingleInstance(dirs).owner_pid() is None


def test_a_launch_gives_up_on_a_holder_that_never_answers(dirs: DataDirs) -> None:
    running = SingleInstance(dirs)
    assert running.try_acquire()
    try:
        launch = SingleInstance(dirs, server_name=nobody_listens())
        started = time.monotonic()

        assert launch.signal_existing(wait_ms=300) is Answer.SILENT

        assert time.monotonic() - started >= 0.3
        assert not SingleInstance(dirs).try_acquire(), "the holder must keep its lock"
    finally:
        running.release()


def test_a_launch_takes_the_lock_of_a_holder_that_exits_while_it_waits(dirs: DataDirs) -> None:
    running = SingleInstance(dirs)
    assert running.try_acquire()
    exit_later = threading.Timer(0.2, running.release)
    exit_later.start()
    launch = SingleInstance(dirs, server_name=nobody_listens())
    try:
        started = time.monotonic()

        assert launch.signal_existing(wait_ms=5000) is Answer.TOOK_OVER

        assert time.monotonic() - started < 2, "it waited out the whole budget"
        assert not SingleInstance(dirs).try_acquire(), "the lock is the launch's now"
    finally:
        exit_later.join()
        launch.release()


def test_a_launch_takes_the_place_of_a_copy_that_quits_without_reading_it(
    dirs: DataDirs,
) -> None:
    name = nobody_listens()
    quitting = subprocess.Popen(
        [sys.executable, "-c", QUITTING_COPY, str(dirs.root), name, "0.5"],
        stdout=subprocess.PIPE,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(map_overlay.__file__).parents[1])},
    )
    launch = SingleInstance(dirs, server_name=name)
    try:
        assert quitting.stdout is not None
        assert quitting.stdout.readline() == "listening\n"

        assert launch.signal_existing(wait_ms=5000) is Answer.TOOK_OVER

        assert quitting.wait(timeout=10) == 0
    finally:
        quitting.kill()
        quitting.wait()
        launch.release()
