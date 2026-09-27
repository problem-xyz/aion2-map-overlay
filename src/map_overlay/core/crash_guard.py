"""What a native crash in the last run says to turn off in this one.

Two things in the process drive the graphics driver's Direct3D 11 code, where the first
reported crash happened (amdxx64.dll): dxcam's screen capture on the engine thread, and Qt
WebEngine, which on OpenGL imports every frame Chromium draws from Direct3D 11 through the
driver's interop, on the GUI thread. The crash trace core/logs.py leaves says which thread
faulted, so the next start turns off the path it faulted in, and keeps it off: mss instead of
dxcam, or Qt on Direct3D 11 instead of OpenGL. Each is slower or less smooth than what it
replaces, which is why neither is the default.

A crash on some other thread of ours turns nothing off: there is no safer path to fall back to.
"""

import itertools
import logging
import re
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path

from map_overlay.core.fileio import atomic_write_json, read_json_or_none
from map_overlay.core.logs import CLEAN_EXIT, CRASH_NAME
from map_overlay.core.paths import DataDirs

log = logging.getLogger(__name__)

FALLBACKS_NAME = "fallbacks.json"

_SESSION = re.compile(r"^--- \d{4}-\d{2}-\d{2} ")
_FATAL = re.compile(r"^(Windows fatal exception|Fatal Python error): ")
# The bottom frame of the GUI thread: app.main, running the Qt event loop.
_GUI_THREAD = re.compile(r'app\.py", line \d+ in main$', re.MULTILINE)


class CrashSite(StrEnum):
    CAPTURE = "capture"  # the engine thread, inside dxcam
    GUI = "gui"  # the GUI thread, or a native thread Python has no stack for
    WORKER = "worker"  # any other thread of ours


@dataclass(frozen=True)
class Fallbacks:
    """The slower paths this machine has been moved to, one per crash site."""

    direct3d: bool = False  # Qt draws through Direct3D 11, not OpenGL
    mss: bool = False  # the screen is captured through mss, not dxcam

    def after(self, site: CrashSite | None) -> Fallbacks:
        if site is CrashSite.GUI:
            return replace(self, direct3d=True)
        if site is CrashSite.CAPTURE:
            return replace(self, mss=True)
        return self


def last_crash(trace: str) -> CrashSite | None:
    """Where the last session in a crash trace died, or None if it did not.

    On Windows faulthandler also writes exceptions that native code catches and survives, so
    a fatal entry alone is not a crash: a session that reached its clean-exit line was not one.
    """
    lines = trace.splitlines()
    starts = [i for i, line in enumerate(lines) if _SESSION.match(line)]
    session = lines[starts[-1] :] if starts else lines
    if CLEAN_EXIT in session:
        return None
    fatal = [i for i, line in enumerate(session) if _FATAL.match(line)]
    if not fatal:
        return None
    return _site(session[fatal[-1] :])


def _site(entry: list[str]) -> CrashSite:
    for i, line in enumerate(entry):
        if line.startswith("Current thread "):
            frames = "\n".join(itertools.takewhile(str.strip, entry[i + 1 :]))
            break
    else:
        return CrashSite.GUI
    if "dxcam" in frames or "capture.py" in frames:
        return CrashSite.CAPTURE
    if _GUI_THREAD.search(frames):
        return CrashSite.GUI
    return CrashSite.WORKER


def load_fallbacks(path: Path) -> Fallbacks:
    raw = read_json_or_none(path)
    if not isinstance(raw, dict):
        return Fallbacks()
    return Fallbacks(direct3d=raw.get("direct3d") is True, mss=raw.get("mss") is True)


def read_last_crash(dirs: DataDirs) -> CrashSite | None:
    """Where the last run crashed, if it did.

    Has to run before setup_logging, whose session header would make the crashed run no longer
    the last one in the trace.
    """
    try:
        trace = (dirs.logs / CRASH_NAME).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return last_crash(trace)


def apply_crash(dirs: DataDirs, site: CrashSite | None) -> tuple[Fallbacks, bool]:
    """The fallbacks to run with, and whether this crash added one."""
    path = dirs.root / FALLBACKS_NAME
    before = load_fallbacks(path)
    after = before.after(site)
    if after == before:
        return before, False
    try:
        atomic_write_json(path, asdict(after))
    except OSError:
        # Still run on the fallback now; the next crash will ask for it again.
        log.exception("cannot save %s", path)
    return after, True
