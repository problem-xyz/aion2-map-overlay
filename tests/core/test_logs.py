"""The crash trace: what is left behind when native code takes the process down.

The crash happens in a child process, because faulthandler and the root logger are
process-wide and a real access violation ends the process that has it.
"""

import subprocess
import sys
from pathlib import Path

from map_overlay.core.logs import CRASH_NAME, MAX_BYTES

# Faults on a thread of its own, so the trace has to show more than the main thread.
CRASHING_COPY = """
import ctypes, faulthandler, sys, threading
from pathlib import Path
from map_overlay.core.logs import setup_logging
from map_overlay.core.paths import DataDirs

setup_logging(DataDirs.from_root(Path(sys.argv[1])))
if sys.platform == "win32":
    ctypes.windll.kernel32.SetErrorMode(0x0002)  # no Windows Error Reporting dialog

def capture_thread_body():
    faulthandler._read_null()  # a real access violation, as a driver would take

worker = threading.Thread(target=capture_thread_body)
worker.start()
worker.join()
"""


def _crash(root: Path) -> str:
    done = subprocess.run(
        [sys.executable, "-c", CRASHING_COPY, str(root)],
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert done.returncode != 0
    return (root / "logs" / CRASH_NAME).read_text(encoding="utf-8")


def test_a_native_crash_leaves_every_threads_stack(tmp_path: Path) -> None:
    trace = _crash(tmp_path)

    assert "pid" in trace.splitlines()[0]
    assert "capture_thread_body" in trace
    assert "Current thread" in trace
    assert trace.count("Thread 0x") + trace.count("Current thread 0x") >= 2


def test_a_restart_keeps_the_last_crash(tmp_path: Path) -> None:
    _crash(tmp_path)
    trace = _crash(tmp_path)

    assert trace.count("Current thread 0x") == 2


def test_an_oversized_trace_starts_over(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / CRASH_NAME).write_text("x" * (MAX_BYTES + 1), encoding="utf-8")

    trace = _crash(tmp_path)

    assert "x" * 100 not in trace
    assert "capture_thread_body" in trace
