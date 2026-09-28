"""Entry point: process-wide setup, then the control window.

Bootstrap only. Anything that has to happen before Qt is imported -- DPI awareness above all --
belongs here and nowhere else. The one thing that runs earlier still, Velopack's start-up hook,
lives outside this module, because importing it already has side effects: in __main__.py for a
source run and in packaging/rthook_velopack.py for a build.
"""

import contextlib
import ctypes
import logging
import os
import sys

# Work in physical pixels, so screen-region, capture and overlay coordinates line up 1:1.
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")


def _claim_dpi_awareness() -> None:
    """Claim DPI awareness before anything else in the process can.

    Otherwise dxcam gets there first with the older SetProcessDpiAwareness call, Qt can no
    longer raise the process to per-monitor v2, and it complains on the console. This has to
    run before the engine is imported and before QApplication is created.
    """
    if sys.platform != "win32":
        return
    with contextlib.suppress(AttributeError, OSError):
        user32 = ctypes.windll.user32
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shcore.SetProcessDpiAwareness(2)


_claim_dpi_awareness()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from map_overlay.bridge.backend import Backend  # noqa: E402
from map_overlay.core.appinfo import APP_NAME, ORG_NAME, PACK_ID  # noqa: E402
from map_overlay.core.crash_guard import (  # noqa: E402
    CrashSite,
    apply_crash,
    read_last_crash,
)
from map_overlay.core.logs import (  # noqa: E402
    log_environment,
    log_screens,
    mark_clean_exit,
    route_qt_messages,
    setup_logging,
)

log = logging.getLogger(__name__)
from map_overlay.core.paths import (  # noqa: E402
    DataDirs,
    app_root,
    is_frozen,
    is_portable,
    migrate_dev_layout,
    run_migration,
    user_data_dir,
)
from map_overlay.core.single_instance import Answer, SingleInstance  # noqa: E402
from map_overlay.qt import win32  # noqa: E402
from map_overlay.qt.collector import GuiCollector  # noqa: E402
from map_overlay.qt.control_window import ControlWindow  # noqa: E402
from map_overlay.qt.graphics import choose_graphics_api  # noqa: E402
from map_overlay.vision.capture import Capture  # noqa: E402


def _data_dir_override(argv):
    """--data-dir <path>, or MAP_OVERLAY_DATA_DIR. The flag wins."""
    for i, arg in enumerate(argv):
        if arg == "--data-dir" and i + 1 < len(argv):
            return argv[i + 1]
        if arg.startswith("--data-dir="):
            return arg.split("=", 1)[1]
    return os.environ.get("MAP_OVERLAY_DATA_DIR")


def _dev_requested(argv) -> bool:
    """--dev, unless this is a build, where it points at a dev server that is not running.

    Honouring it there would load the Vite URL into all three windows and show nothing at all,
    which looks like a broken build rather than a flag that does not apply.
    """
    if "--dev" not in argv:
        return False
    if is_frozen():
        log.warning("--dev ignored: this is a build, and there is no dev server to attach to")
        return False
    return True


def main():
    dirs = DataDirs.from_root(user_data_dir(_data_dir_override(sys.argv)))
    # Two copies would fight over the same settings, progress and capture region, so the
    # second launch raises the first instead of starting beside it. It has to find out before
    # it touches the data: migrate_dev_layout moves whole directories, and two processes must
    # not do that at once. The lock's own directory is all that is made before it.
    dirs.root.mkdir(parents=True, exist_ok=True)
    instance = SingleInstance(dirs)
    first = instance.try_acquire()
    crashed_in = read_last_crash(dirs)  # before setup_logging starts a session of its own
    setup_logging(dirs)
    answer = None if first else _raise_running_copy(instance)
    if answer is Answer.RAISED:
        log.info("another instance is already running; raised it and exiting")
        return 0
    route_qt_messages()  # only now: it would hang the wait above
    log_environment()
    if answer is Answer.SILENT:
        log.warning("the lock is held but nobody answered; starting anyway")

    dev = _dev_requested(sys.argv)
    # Migrate before ensure(): an empty directory created here would look like a destination
    # that already holds data, and the move would be skipped. setup_logging above only made
    # logs/, which is not one of the entries it moves, and a failure leaves its traceback there.
    moved = run_migration(
        "moving the pre-userdata layout", lambda: migrate_dev_layout(app_root(), dirs)
    )
    dirs.ensure()
    fallbacks, fell_back = apply_crash(dirs, crashed_in)
    if crashed_in is not None:
        log.warning("the last run crashed in native code, on the %s thread", crashed_in)
    Capture.dxcam_allowed = not fallbacks.mss

    if not is_frozen():
        # A build is its own exe and gets its identity from it and from Velopack's shortcuts;
        # a source run is python.exe, and would sit under Python's icon on the taskbar.
        win32.set_app_user_model_id(f"{ORG_NAME}.{PACK_ID}.Source")
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    if is_portable():
        # Qt Quick, which QtWebEngine draws through, caches compiled pipelines under
        # QStandardPaths::CacheLocation -- %LocalAppData%\<app>\cache, which cannot be
        # moved anywhere else on Windows. A portable copy has to leave nothing behind on the
        # machine it ran on, so it recompiles instead: tens of milliseconds at start-up.
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_DisableShaderDiskCache, True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # Before Backend: its threads must never be the ones a garbage collection runs on.
    collector = GuiCollector(app)  # noqa: F841 -- kept alive by this frame until exec() returns
    log_screens()
    choose_graphics_api(allow_opengl=not fallbacks.direct3d)

    backend = Backend(dirs, dev=dev)
    if moved is None:
        backend.queue_notice("data.migration_failed", "warning", path=str(app_root()))
    elif moved:
        backend.queue_notice("data.migrated", path=str(dirs.root))
    if fell_back:
        notice = "crash.capture" if crashed_in is CrashSite.CAPTURE else "crash.graphics"
        backend.queue_notice(notice, "warning")
    window = ControlWindow(backend, dev)
    backend.setParent(window)
    # closeEvent does not fire on log-off or a Qt-level quit; the settings must still land.
    app.aboutToQuit.connect(backend._store.flush)
    window.show()
    instance.listen(lambda: _raise_window(window))
    app.aboutToQuit.connect(instance.release)
    code = app.exec()
    mark_clean_exit()
    # After aboutToQuit has flushed the settings and released the lock: Update.exe may apply a
    # downloaded update as soon as it starts, without waiting for this process to be gone.
    backend.hand_over_update()
    return code


def _raise_running_copy(instance: SingleInstance) -> Answer:
    """Ask the copy holding the lock to come forward, waiting for one that is still starting.

    No QApplication is needed for this, so a second launch leaves before it has built one.
    """
    win32.allow_set_foreground(instance.owner_pid())
    return instance.signal_existing()


def _raise_window(window) -> None:
    """Bring the existing window forward, whatever state it was left in.

    activateWindow() can take the foreground only because the launch that asked has handed
    over its right to it (see _raise_running_copy); without that it flashes the taskbar button.
    """
    window.show()
    window.setWindowState(
        window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive
    )
    window.raise_()
    window.activateWindow()


if __name__ == "__main__":
    sys.exit(main())
