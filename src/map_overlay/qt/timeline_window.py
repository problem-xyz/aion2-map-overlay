"""The day timeline: the built page again, opened in its `#timeline` mode, in a window of its own.

An ordinary application window, not one over the game: a wide view of the day is read before a
session, not during a fight, and the panel is too narrow for it.
"""

import logging
from collections.abc import Callable

from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QMainWindow

from map_overlay.core.settings import Region
from map_overlay.i18n.catalog import t
from map_overlay.qt.webview import attach_backend

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 1200, 640
MIN_WIDTH, MIN_HEIGHT = 720, 360


def _on_a_screen(rect: QRect) -> bool:
    """Whether enough of the window to grab its title bar lies on some screen."""
    return any(
        screen.availableGeometry().intersected(rect).width() >= 120
        for screen in QGuiApplication.screens()
    )


class TimelineWindow(QMainWindow):
    """Built once and hidden rather than destroyed, like the editor: it opens again as it was.

    `on_moved` hears where the window was left whenever it hides; the caller keeps that in state.
    The page closes it on Esc through `closeTimersTimeline()`.
    """

    def __init__(
        self, backend, url, scale: float, region: Region | None, on_moved: Callable[[Region], None]
    ) -> None:
        super().__init__()
        self.setWindowTitle(t("native.window.timeline"))
        self.setMinimumSize(int(MIN_WIDTH * scale), int(MIN_HEIGHT * scale))
        self._on_moved = on_moved
        self._place(region, scale)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.channel = attach_backend(self.view, backend)
        self.view.setZoomFactor(scale)
        self.view.setUrl(url)

    def _place(self, region: Region | None, scale: float) -> None:
        if region:
            rect = QRect(region["left"], region["top"], region["width"], region["height"])
            if _on_a_screen(rect):
                self.setGeometry(rect)
                return
        self.resize(int(WIDTH * scale), int(HEIGHT * scale))
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            frame = self.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.move(frame.topLeft())

    def region(self) -> Region:
        g = self.geometry()
        return {"left": g.x(), "top": g.y(), "width": g.width(), "height": g.height()}

    def hideEvent(self, event) -> None:
        # Not on every move: a drag would rewrite state.json dozens of times a second
        if not self.isMinimized():
            self._on_moved(self.region())
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.hide()

    def force_close(self) -> None:
        """Application is going down: detach the channel first, as the editor does."""
        if self.channel is not None:
            # Qt takes nullptr here to detach; PySide6's stubs do not allow None.
            self.view.page().setWebChannel(None)  # pyright: ignore[reportArgumentType]
            self.channel = None
        self.hide()
        QTimer.singleShot(0, self.deleteLater)

    def retitle(self) -> None:
        self.setWindowTitle(t("native.window.timeline"))
