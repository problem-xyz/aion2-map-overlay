"""The monitors Qt sees, as plain rectangles, and one signal for when that set changes.

QT_ENABLE_HIGHDPI_SCALING=0 is set before Qt is imported (map_overlay/app.py), so a QScreen
geometry is in physical pixels -- the same coordinates the region picker hands out and capture
reads. The rectangles are handed to core/geometry.py, which holds the logic.
"""

import logging

from PySide6.QtCore import QObject, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QScreen

from map_overlay.core.geometry import Rect

log = logging.getLogger(__name__)

# Unplugging a monitor arrives as a burst: screenRemoved, primaryScreenChanged and a
# geometryChanged on every screen that moved. One check after the burst settles is enough,
# and it also rides out a monitor that drops off for a moment and comes straight back.
SCREEN_SETTLE_MS = 1000


def _rect(geometry: QRect) -> Rect:
    return (geometry.x(), geometry.y(), geometry.width(), geometry.height())


def screen_rects() -> list[Rect]:
    """Every screen's geometry in virtual-desktop coordinates."""
    return [_rect(screen.geometry()) for screen in QGuiApplication.screens()]


def primary_rect() -> Rect | None:
    screen = QGuiApplication.primaryScreen()
    return _rect(screen.geometry()) if screen is not None else None


class ScreenWatcher(QObject):
    """Emits `changed` once the monitor layout has changed and stopped changing.

    GUI thread only; the QGuiApplication must exist before this is built. close() it on
    shutdown: the application's signals outlive the owner, and a check fired after it would
    run against windows and files that are already gone.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None, settle_ms: int = SCREEN_SETTLE_MS) -> None:
        super().__init__(parent)
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(settle_ms)
        self._timer.timeout.connect(self._fire)

        app = QGuiApplication.instance()
        if not isinstance(app, QGuiApplication):
            log.warning("no QGuiApplication: monitor changes will not be noticed")
            return
        app.screenAdded.connect(self._on_added)
        app.screenRemoved.connect(self._schedule)
        app.primaryScreenChanged.connect(self._schedule)
        for screen in QGuiApplication.screens():
            screen.geometryChanged.connect(self._schedule)

    def _on_added(self, screen: QScreen) -> None:
        screen.geometryChanged.connect(self._schedule)
        self._schedule()

    def close(self) -> None:
        self._closed = True
        self._timer.stop()

    def _schedule(self, *_args: object) -> None:
        if not self._closed:
            self._timer.start()

    def _fire(self) -> None:
        log.info("monitor layout changed: %s", screen_rects())
        self.changed.emit()
