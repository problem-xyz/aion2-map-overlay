"""Dimming the screen so the user can drag out the area the game shows the map in."""

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from map_overlay.i18n.catalog import t


class RegionSelector(QWidget):
    """Dims a screen and lets the user drag a rectangle out of it.

    Exactly one of `selected` or `cancelled` is emitted, and the window has closed itself by
    then; a rectangle under 50x50 counts as a cancellation, not a region. `selected` carries
    the region in screen coordinates -- the left/top/width/height dict the rest of the app
    passes around -- not in widget coordinates.

    The caller owns the instance and must drop it with `deleteLater()` from a connected slot,
    never from inside the emission.
    """

    selected = Signal(dict)
    cancelled = Signal()

    DEFAULT_PROMPT = t("native.selector.prompt")
    # Start with no map area yet: the same box, and the overlay comes up as soon as it is drawn
    START_PROMPT = t("native.selector.promptStart")

    def __init__(self, screen_geometry, prompt=DEFAULT_PROMPT) -> None:
        super().__init__()
        self._begin = None
        self._end = None
        self._prompt = prompt
        self.setWindowTitle(t("native.window.selector"))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen_geometry)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))
        if self._begin is not None and self._end is not None:
            r = QRect(self._begin, self._end).normalized()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.fillRect(r, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(120, 200, 255), 2))
            p.drawRect(r)
            p.setPen(Qt.GlobalColor.white)
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(r.left(), r.top() - 8, f"{r.width()} × {r.height()}")
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Segoe UI", 16))
        p.drawText(30, 50, self._prompt)
        p.end()

    def mousePressEvent(self, event) -> None:
        self._begin = self._end = event.position().toPoint()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._begin is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._begin is None:
            return
        r = QRect(self._begin, event.position().toPoint()).normalized()
        self.close()
        if r.width() < 50 or r.height() < 50:
            self.cancelled.emit()
            return
        self.selected.emit(
            {
                "left": self.x() + r.x(),
                "top": self.y() + r.y(),
                "width": r.width(),
                "height": r.height(),
            }
        )

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()

    def retitle(self) -> None:
        """Re-read the title after a language change; see WindowManager.retitle."""
        self.setWindowTitle(t("native.window.selector"))
