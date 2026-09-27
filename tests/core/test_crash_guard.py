"""Reading the last run's crash trace, and the fallback it earns.

The hand-written traces follow what faulthandler writes on Windows; the two tests at the end
crash a real child process, so a change in that format shows up here and not on a player's
machine.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from map_overlay.core.crash_guard import (
    FALLBACKS_NAME,
    CrashSite,
    Fallbacks,
    apply_crash,
    last_crash,
    load_fallbacks,
    read_last_crash,
)
from map_overlay.core.paths import DataDirs

HEADER = "--- 2026-09-27 22:41:25 pid 15524 1.0.0"

GUI_CRASH = """\
Windows fatal exception: access violation

Thread 0x00002a10 (most recent call first):
  File "map_overlay\\vision\\engine.py", line 246 in _grab
  File "map_overlay\\vision\\engine.py", line 419 in run

Current thread 0x00003ca4 (most recent call first):
  File "map_overlay\\app.py", line 163 in main
  File "map_overlay\\__main__.py", line 28 in <module>
"""

CAPTURE_CRASH = """\
Windows fatal exception: access violation

Current thread 0x00002a10 (most recent call first):
  File "dxcam\\dxcam.py", line 381 in _copy_region_to_stage
  File "dxcam\\dxcam.py", line 312 in _grab
  File "map_overlay\\vision\\capture.py", line 77 in grab
  File "map_overlay\\vision\\engine.py", line 246 in _grab

Thread 0x00003ca4 (most recent call first):
  File "map_overlay\\app.py", line 163 in main
"""

WORKER_CRASH = """\
Windows fatal exception: access violation

Current thread 0x00001b2c (most recent call first):
  File "map_overlay\\vision\\detector.py", line 120 in run

Thread 0x00003ca4 (most recent call first):
  File "map_overlay\\app.py", line 163 in main
"""

# A native thread Python never ran on: there is no "Current thread" block at all.
NATIVE_THREAD_CRASH = """\
Windows fatal exception: access violation

Thread 0x00003ca4 (most recent call first):
  File "map_overlay\\app.py", line 163 in main
"""


def _session(*parts: str) -> str:
    return "\n".join([HEADER, *parts])


@pytest.mark.parametrize(
    ("entry", "site"),
    [
        (GUI_CRASH, CrashSite.GUI),
        (CAPTURE_CRASH, CrashSite.CAPTURE),
        (WORKER_CRASH, CrashSite.WORKER),
        (NATIVE_THREAD_CRASH, CrashSite.GUI),
    ],
)
def test_the_faulting_thread_names_the_site(entry: str, site: CrashSite) -> None:
    assert last_crash(_session(entry)) is site


def test_a_session_that_exited_cleanly_did_not_crash() -> None:
    # faulthandler also writes an exception that native code caught and survived.
    assert last_crash(_session(GUI_CRASH, "--- clean exit")) is None


def test_a_session_with_nothing_fatal_did_not_crash() -> None:
    assert last_crash(HEADER + "\n") is None
    assert last_crash("") is None


def test_only_the_last_session_counts() -> None:
    trace = "\n".join([_session(GUI_CRASH), _session("--- clean exit"), HEADER])
    assert last_crash(trace) is None


def test_the_last_entry_of_a_session_is_the_one_that_killed_it() -> None:
    assert last_crash(_session(WORKER_CRASH, CAPTURE_CRASH)) is CrashSite.CAPTURE


def _dirs(tmp_path: Path, trace: str | None = None) -> DataDirs:
    dirs = DataDirs.from_root(tmp_path)
    dirs.ensure()
    if trace is not None:
        (dirs.logs / "crash.log").write_text(trace, encoding="utf-8")
    return dirs


def test_no_trace_is_no_crash(tmp_path: Path) -> None:
    assert read_last_crash(_dirs(tmp_path)) is None


def test_a_crash_turns_its_path_off_for_good(tmp_path: Path) -> None:
    dirs = _dirs(tmp_path)

    fallbacks, changed = apply_crash(dirs, CrashSite.CAPTURE)
    assert (fallbacks, changed) == (Fallbacks(mss=True), True)

    fallbacks, changed = apply_crash(dirs, None)
    assert (fallbacks, changed) == (Fallbacks(mss=True), False)

    fallbacks, changed = apply_crash(dirs, CrashSite.GUI)
    assert (fallbacks, changed) == (Fallbacks(direct3d=True, mss=True), True)
    assert load_fallbacks(dirs.root / FALLBACKS_NAME) == fallbacks


def test_a_repeat_crash_changes_nothing(tmp_path: Path) -> None:
    dirs = _dirs(tmp_path)
    apply_crash(dirs, CrashSite.GUI)

    assert apply_crash(dirs, CrashSite.GUI) == (Fallbacks(direct3d=True), False)


def test_a_worker_crash_has_nothing_to_turn_off(tmp_path: Path) -> None:
    dirs = _dirs(tmp_path)

    assert apply_crash(dirs, CrashSite.WORKER) == (Fallbacks(), False)
    assert not (dirs.root / FALLBACKS_NAME).exists()


def test_a_damaged_fallbacks_file_reads_as_none_taken(tmp_path: Path) -> None:
    (tmp_path / FALLBACKS_NAME).write_text("{not json", encoding="utf-8")
    assert load_fallbacks(tmp_path / FALLBACKS_NAME) == Fallbacks()


# The crashing function sits in a file named like the module the classifier looks for.
CRASHING_MODULE = """
import ctypes, faulthandler

def main():
    faulthandler._read_null()  # a real access violation, as a driver would take

def grab():
    faulthandler._read_null()
"""

RUNNER = """
import ctypes, sys, threading
from pathlib import Path
from map_overlay.core.logs import setup_logging
from map_overlay.core.paths import DataDirs

setup_logging(DataDirs.from_root(Path(sys.argv[1])))
ctypes.windll.kernel32.SetErrorMode(0x0002)  # no Windows Error Reporting dialog
sys.path.insert(0, sys.argv[2])
module = __import__(sys.argv[3])
if sys.argv[4] == "main":
    module.main()
else:
    worker = threading.Thread(target=module.grab)
    worker.start()
    worker.join()
"""


@pytest.mark.skipif(sys.platform != "win32", reason="the app and its crash traces are Windows")
@pytest.mark.parametrize(
    ("module", "call", "site"),
    [("app", "main", CrashSite.GUI), ("capture", "grab", CrashSite.CAPTURE)],
)
def test_a_real_crash_is_read_back(tmp_path: Path, module: str, call: str, site: CrashSite) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / f"{module}.py").write_text(CRASHING_MODULE, encoding="utf-8")
    root = tmp_path / "data"

    done = subprocess.run(
        [sys.executable, "-c", RUNNER, str(root), str(source), module, call],
        capture_output=True,
        timeout=60,
        check=False,
    )

    assert done.returncode != 0
    assert read_last_crash(DataDirs.from_root(root)) is site
