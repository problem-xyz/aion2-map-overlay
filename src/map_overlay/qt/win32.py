"""Every ctypes call into Windows lives here, wrapped so callers never see ctypes.

Each wrapper returns a plain bool or number and answers with a safe default off Windows, so
nothing above this module imports ctypes or branches on the platform.

The convention also asks a wrapper to catch OSError and AttributeError itself, so that an
entry point missing on an older build degrades instead of surfacing as a traceback in the
GUI. allow_set_foreground, set_capture_affinity and windows_version do.
"""

import ctypes
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget

log = logging.getLogger(__name__)

ASFW_ANY = 0xFFFFFFFF  # (DWORD)-1: any process may take the foreground

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000

# SetWindowDisplayAffinity: visible to capture, or excluded from it.
WDA_NONE = 0x00
WDA_EXCLUDEFROMCAPTURE = 0x11

# Windows 10 version 2004. An older Windows does not know WDA_EXCLUDEFROMCAPTURE and applies
# WDA_MONITOR in its place, which paints the window black in every capture -- the engine's
# own included, so the map under the overlay could never be found.
CAPTURE_EXCLUSION_MIN_VERSION = (10, 0, 19041)


class _OsVersionInfoExW(ctypes.Structure):
    _fields_ = (
        ("dwOSVersionInfoSize", ctypes.c_ulong),
        ("dwMajorVersion", ctypes.c_ulong),
        ("dwMinorVersion", ctypes.c_ulong),
        ("dwBuildNumber", ctypes.c_ulong),
        ("dwPlatformId", ctypes.c_ulong),
        ("szCSDVersion", ctypes.c_wchar * 128),
        ("wServicePackMajor", ctypes.c_ushort),
        ("wServicePackMinor", ctypes.c_ushort),
        ("wSuiteMask", ctypes.c_ushort),
        ("wProductType", ctypes.c_ubyte),
        ("wReserved", ctypes.c_ubyte),
    )


def windows_version() -> tuple[int, int, int] | None:
    """(major, minor, build) of the running Windows, or None off Windows or on failure.

    RtlGetVersion rather than GetVersionEx or platform.version(): those answer through the
    compatibility shims, and a process started in compatibility mode is told it runs an older
    Windows than it does.
    """
    if sys.platform != "win32":
        return None
    info = _OsVersionInfoExW()
    info.dwOSVersionInfoSize = ctypes.sizeof(info)
    try:
        status = ctypes.windll.ntdll.RtlGetVersion(ctypes.byref(info))
    except OSError, AttributeError:
        log.exception("RtlGetVersion failed")
        return None
    if status != 0:
        log.warning("RtlGetVersion returned NTSTATUS 0x%08x", status & 0xFFFFFFFF)
        return None
    return (info.dwMajorVersion, info.dwMinorVersion, info.dwBuildNumber)


def supports_capture_exclusion(version: tuple[int, int, int] | None) -> bool:
    """Can a window be hidden from screen capture on this Windows?

    An unknown version -- not Windows, or RtlGetVersion failed -- counts as yes: telling a user
    their Windows is too old when it may not be is worse than the default it would change.
    """
    return version is None or version >= CAPTURE_EXCLUSION_MIN_VERSION


def set_capture_affinity(widget: QWidget, recordable: bool) -> bool:
    """Let screen-capture software see the window, or hide it from capture (Windows 10 2004+).

    The overlay is excluded by default: the engine captures the same screen region and would
    otherwise feature-match the map against its own route. Recording a video needs it visible,
    and then it lands both in OBS and in the engine's own frames. On a Windows older than
    CAPTURE_EXCLUSION_MIN_VERSION the caller has to pass recordable=True every time: exclusion
    there turns into a black box in the engine's frames.

    Returns:
        True if Windows accepted the change.
    """
    if sys.platform != "win32":
        return False
    affinity = WDA_NONE if recordable else WDA_EXCLUDEFROMCAPTURE
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), affinity))
    except OSError, AttributeError:
        log.exception("SetWindowDisplayAffinity failed")
        return False


def allow_set_foreground(pid: int | None) -> bool:
    """Let another process bring its window to the front, or any process if pid is None.

    Windows lets only the foreground process move the foreground. A second launch is that
    process, because the user just started it; the running copy it asks to come forward is
    not, and its activateWindow() alone would only flash its taskbar button.

    Returns:
        True if Windows granted it. It refuses when this process is not in the foreground.
    """
    if sys.platform != "win32":
        return False
    try:
        grant = ctypes.windll.user32.AllowSetForegroundWindow
        return bool(grant(ctypes.c_ulong(ASFW_ANY if pid is None else pid)))
    except OSError, AttributeError:
        return False


def set_app_user_model_id(app_id: str) -> bool:
    """Give the process its own taskbar identity, set before any window is shown.

    Without one, the taskbar groups a source run under python.exe and shows Python's icon on
    the button instead of the window's.

    Returns:
        True if Windows took it.
    """
    if sys.platform != "win32":
        return False
    try:
        set_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_id.argtypes = [ctypes.c_wchar_p]
        set_id.restype = ctypes.c_long
        return set_id(app_id) == 0  # S_OK
    except OSError, AttributeError:
        return False
