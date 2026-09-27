"""Logging setup: a rotating file, the console when there is one, and every escape hatch.

A user reporting "the overlay stopped following the map" cannot paste a stack trace that was
printed to a console that does not exist -- a windowed build has no stdout at all. So the log
goes to a file under the user's data directory, and everything that can raise off the main
path is routed into it: uncaught exceptions on any thread, Qt's own warnings, and the messages
the React pages write to their console. A crash in native code -- a graphics driver, Qt --
kills the process before any of that runs, so faulthandler writes the Python stack of every
thread to a file of its own.

The header written at start-up is there because most reports come down to which capture
backend, which Qt build or which monitor layout the user has.
"""

import faulthandler
import logging
import logging.handlers
import os
import platform
import sys
import threading
import time
from types import TracebackType
from typing import Any

from map_overlay import __version__
from map_overlay.core.appinfo import APP_NAME
from map_overlay.core.paths import DataDirs

log = logging.getLogger(__name__)

LOG_NAME = "map-overlay.log"
CRASH_NAME = "crash.log"
MAX_BYTES = 1_000_000
BACKUP_COUNT = 3
FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Qt's own severities, mapped onto ours. Qt warnings are mostly noise worth keeping but not
# worth alarming anyone with.
_QT_LEVELS = {
    0: logging.DEBUG,
    1: logging.WARNING,
    2: logging.WARNING,
    3: logging.ERROR,
    4: logging.CRITICAL,
}


def _has_console() -> bool:
    """A windowed build has no stderr; writing to it then raises or silently vanishes."""
    return sys.stderr is not None and getattr(sys.stderr, "fileno", None) is not None


def _install_excepthooks() -> None:
    def hook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logging.getLogger("unhandled").critical("uncaught exception", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook

    def thread_hook(args: Any) -> None:
        if issubclass(args.exc_type, SystemExit):
            return
        logging.getLogger("unhandled").critical(
            "uncaught exception in thread %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = thread_hook


def _enable_crash_trace(dirs: DataDirs) -> None:
    """On a native crash, write where every thread was to crash.log.

    Windows' own report names only the DLL that faulted. The Python stacks tell which of our
    threads was inside it: the engine's capture calls or the GUI thread's event loop.

    The file is appended to rather than replaced, so a restart after a crash does not wipe the
    trace before anyone has seen it. It starts over once it grows past MAX_BYTES: on Windows
    faulthandler also writes exceptions that native code goes on to handle, and nothing else
    would bound it.
    """
    path = dirs.logs / CRASH_NAME
    mode = "w" if path.exists() and path.stat().st_size > MAX_BYTES else "a"
    # Left open for the life of the process: faulthandler writes to its descriptor.
    trace = path.open(mode, encoding="utf-8")
    trace.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} pid {os.getpid()} {__version__}\n")
    trace.flush()
    faulthandler.enable(trace, all_threads=True)


def route_qt_messages() -> None:
    """Route Qt's own diagnostics into the log instead of a console nobody is watching.

    Kept out of setup_logging because a second launch must not have it yet. A Python handler
    needs the GIL, and Qt calls it from a pipe's worker thread when the running copy hangs up
    on a request -- while SingleInstance.signal_existing holds the GIL in a wait on that very
    worker. The two then block each other for good, and the launch never exits.
    """
    # Imported here, not at module scope: core/ stays importable without Qt, so tests and
    # tooling can use the logging setup without pulling in a GUI toolkit.
    try:
        from PySide6.QtCore import qInstallMessageHandler  # noqa: PLC0415
    except ImportError:  # pragma: no cover - Qt is always present in the app
        return

    qt_log = logging.getLogger("qt")

    def handler(mode: Any, _context: Any, message: str) -> None:
        qt_log.log(_QT_LEVELS.get(int(mode), logging.INFO), "%s", message)

    qInstallMessageHandler(handler)


def log_environment() -> None:
    """The start-up header, kept out of setup_logging for the sake of a second launch.

    That process logs why it is leaving into the running copy's log, where a header would read
    as a restart of the running copy.
    """
    log.info("%s %s starting", APP_NAME, __version__)
    log.info("python %s on %s %s", sys.version.split()[0], platform.system(), platform.release())
    log.info("frozen=%s executable=%s", getattr(sys, "frozen", False), sys.executable)

    for name, module in (("PySide6", "PySide6"), ("cv2", "cv2"), ("numpy", "numpy")):
        try:
            mod = __import__(module)
            log.info("%s %s", name, getattr(mod, "__version__", "?"))
        except ImportError:
            log.info("%s not available", name)


def log_screens() -> None:
    """Monitor layout. Separate from the header: it needs a live QApplication."""
    try:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415 -- see route_qt_messages
    except ImportError:  # pragma: no cover
        return
    app = QApplication.instance()
    if app is None:
        return
    for i, screen in enumerate(QApplication.screens()):
        g = screen.geometry()
        log.info(
            "screen %d: %dx%d at %d,%d dpr=%.2f%s",
            i,
            g.width(),
            g.height(),
            g.x(),
            g.y(),
            screen.devicePixelRatio(),
            " (primary)" if screen is QApplication.primaryScreen() else "",
        )


def setup_logging(dirs: DataDirs, level: int = logging.INFO) -> None:
    """Install handlers and hooks. Safe to call once, early, before anything else logs.

    Qt's own messages are not among them: route_qt_messages() adds those.
    """
    dirs.logs.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    formatter = logging.Formatter(FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        dirs.logs / LOG_NAME, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    if _has_console():
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        root.addHandler(stream)

    _install_excepthooks()
    _enable_crash_trace(dirs)
