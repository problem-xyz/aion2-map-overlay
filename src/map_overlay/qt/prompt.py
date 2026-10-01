"""A question over the game, answered with a click: the one place the overlay takes the mouse.

The overlay itself lets every click through to the game. A question needs two buttons, so it is
a window of its own, laid over the bottom of the map area where the overlay's strip is, and it
takes clicks without taking the keyboard: the game stays the window being played.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from map_overlay.i18n.catalog import t
from map_overlay.qt.overlay import ClickThroughWindow
from map_overlay.qt.webview import system_dpi_scale

# As the overlay's strip draws them, so the question reads as part of it.
_STYLE = """
QFrame#strip {{ background: rgb(15, 17, 22); border-top: 1px solid rgba(255, 255, 255, 36); }}
QLabel#title {{ color: #f2f4f8; font-weight: bold; font-size: {title}px; }}
QLabel#detail {{ color: #aeb6c4; font-size: {text}px; }}
QPushButton {{
    color: #f2f4f8; background: rgba(255, 255, 255, 18); font-size: {text}px; font-weight: bold;
    border: 1px solid rgba(255, 255, 255, 50); border-radius: {radius}px;
    padding: {pad_y}px {pad_x}px; min-width: {min_w}px;
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 34); }}
QPushButton#yes {{ color: #12141a; background: #f2b544; border-color: #f2b544; }}
QPushButton#yes:hover {{ background: #f7c662; }}
"""


class PromptWindow(ClickThroughWindow):
    """A yes-or-no question across the bottom of the map area.

    `answered` carries the answer once a button is clicked, and the window hides itself. GUI
    thread only, like every window here.
    """

    answered = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(t("native.window.prompt"))
        self.set_click_through(False)
        k = system_dpi_scale()
        self.setStyleSheet(
            _STYLE.format(
                title=round(15 * k),
                text=round(14 * k),
                radius=round(6 * k),
                pad_y=round(5 * k),
                pad_x=round(14 * k),
                min_w=round(56 * k),
            )
        )
        strip = QFrame(self)
        strip.setObjectName("strip")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(strip)

        self._title = QLabel(strip)
        self._title.setObjectName("title")
        self._detail = QLabel(strip)
        self._detail.setObjectName("detail")
        self._detail.setWordWrap(True)
        self._yes = QPushButton(strip)
        self._yes.setObjectName("yes")
        self._no = QPushButton(strip)
        for button in (self._yes, self._no):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # nothing here takes the keyboard
        self._yes.clicked.connect(lambda: self._answer(True))
        self._no.clicked.connect(lambda: self._answer(False))

        words = QVBoxLayout()
        words.setSpacing(round(2 * k))
        words.addWidget(self._title)
        words.addWidget(self._detail)
        row = QHBoxLayout(strip)
        row.setContentsMargins(round(12 * k), round(8 * k), round(12 * k), round(8 * k))
        row.setSpacing(round(10 * k))
        row.addLayout(words, 1)
        row.addWidget(self._yes)
        row.addWidget(self._no)
        self._region = None

    def ask(self, region, title, detail) -> None:
        """Put the question over the bottom of `region`, the map area, and show it."""
        self._title.setText(title)
        self._detail.setText(detail)
        self._yes.setText(t("native.prompt.yes"))
        self._no.setText(t("native.prompt.no"))
        self._region = dict(region)
        width = int(region["width"])
        self.setFixedWidth(width)
        height = self.layout().totalHeightForWidth(width)  # pyright: ignore[reportOptionalMemberAccess]
        self.setFixedHeight(height)
        self.move(int(region["left"]), int(region["top"] + region["height"] - height))
        if not self.isVisible():
            self.show()
            self.apply_capture_mode()
        self.raise_()

    def asking(self) -> bool:
        return self.isVisible()

    def _answer(self, yes) -> None:
        self.hide()
        self.answered.emit(bool(yes))

    def retitle(self) -> None:
        self.setWindowTitle(t("native.window.prompt"))
