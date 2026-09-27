"""The steps plaque: a small always-on-top window listing the route's steps."""

import json

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCursor, QMouseEvent
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

from map_overlay.core.settings import STEPS_SIZE_SCALE, Region, plaque_scale
from map_overlay.i18n.catalog import current_language, t
from map_overlay.qt.overlay import ClickThroughWindow
from map_overlay.qt.webview import prepare_page, ui_url


def scale_region(region: Region, ratio: float) -> Region:
    """The plaque's rectangle at another zoom: the same top-left corner, the size times ratio."""
    return {
        "left": region["left"],
        "top": region["top"],
        "width": round(region["width"] * ratio),
        "height": round(region["height"] * ratio),
    }


class _PageBridge(QObject):
    """Bridge between the page and the window: the page knows no Qt, the window no DOM.

    Registered on the page's QWebChannel as `steps`. Its six slots are the frozen half of the
    UI contract: the page is built against these exact names.
    """

    dataChanged = Signal(str)

    def __init__(self, window) -> None:
        super().__init__(window)
        self._w = window

    @Slot(result=str)
    def getData(self):
        return self._w.data_json()

    @Slot()
    def dragStart(self) -> None:
        self._w.begin_drag()

    @Slot()
    def dragEnd(self) -> None:
        self._w.end_drag()

    @Slot(str)
    def action(self, name) -> None:
        self._w.actionClicked.emit(name)

    @Slot(int)
    def setHeight(self, height) -> None:
        """Read by nothing since api 18: the user sizes the plaque, and the page fits the rows."""

    @Slot(int, int, int, int)
    def setHotspot(self, x, y, w, h) -> None:
        """The one rectangle of a pinned plaque the mouse still has to reach, window-local."""
        self._w.set_hotspot(QRect(x, y, w, h))


class WebStepsWindow(ClickThroughWindow):
    """The steps plaque: the route's steps list, drawn by the page in its `#steps` mode.

    Ownership is split. The page lays the text out and shows as many rows as the window has
    room for; this window owns the position, the size and everything native. The user moves it
    by its body and sizes it by its right and bottom edges, both only while it is loose. While
    pinned the plaque is click-through except for the hotspot the page registers for its
    buttons.

    Both gestures end on Qt's own mouse release, which reaches the window because Qt captures
    the mouse on a press. They used to end when GetAsyncKeyState said the button was up, and
    Windows says "up" whenever an elevated window -- the game -- is in front: the plaque could
    only be dragged while the panel was.
    """

    # The size a plaque starts at, times the zoom. BASE_WIDTH is the old M, at a factor of 1.
    BASE_WIDTH = 430
    BASE_HEIGHT = 300
    SIZES = STEPS_SIZE_SCALE
    ORDER = ("s", "m", "l")
    # What the three old steps were drawn at, for a page from before the scale
    OLD_FACTORS = {"s": 0.85, "m": 1.0, "l": 1.25}
    MIN_WIDTH = 200
    MIN_HEIGHT = 90  # the head and one row, at a factor of 1
    # How far in from the right and bottom edges a press sizes the plaque rather than moving it.
    # The page draws its resize cursors over the same strips: it is sent the width in its data.
    GRIP = 8
    HOTSPOT_MS = 40  # how often the cursor is checked against the unpin hotspot

    regionChanged = Signal(dict)  # new geometry, once a drag has ended
    actionClicked = Signal(str)  # "size" | "pin" | "close" | "prev" | "next"

    def __init__(self, dev=False) -> None:
        super().__init__()
        self.setWindowTitle(t("native.window.steps"))
        self._steps = []
        self._done = 0
        self._past = 0  # how many steps already passed the plaque keeps, as route_past
        self._title = ""
        self._scale = plaque_scale(1.0)  # the factor drawn at, not the slider's value
        self._pinned = True
        self._hotspot = QRect()
        self._hot = False
        self._grab: QPoint | None = None  # cursor offset from the window corner while dragging
        self._sizing: tuple[str, QPoint, QSize] | None = None  # edges, where it began, size then
        self._pressed_at: QPoint | None = None  # the last left press, in screen coordinates
        self._watched = None  # the QWindow the mouse is watched on, once the window exists

        self.view = QWebEngineView(self)
        # Transparent, or the page paints over the window it is supposed to float above.
        prepare_page(self.view, Qt.GlobalColor.transparent)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._bridge = _PageBridge(self)
        self._channel = QWebChannel(self.view.page())
        self._channel.registerObject("steps", self._bridge)
        self.view.page().setWebChannel(self._channel)
        self.view.setUrl(ui_url(dev, "steps"))

        self._hot_timer = QTimer(self)
        self._hot_timer.setInterval(self.HOTSPOT_MS)
        self._hot_timer.timeout.connect(self._check_hotspot)

    def set_steps(self, steps, done=0, title="") -> None:
        self._steps = list(steps or [])
        self._done = max(0, int(done))
        self._title = str(title or "")
        self._push()

    def set_past(self, past) -> None:
        """How many steps already passed stay on the list, faded, as they stay on the map."""
        past = max(0, int(past))
        if past != self._past:
            self._past = past
            self._push()

    def set_size(self, key) -> None:
        """One of the three old steps, as a scale."""
        if key in self.SIZES:
            self.set_scale(self.SIZES[key])

    def set_scale(self, setting) -> None:
        """The slider's value, steps_scale: the page draws at the factor it stands for.

        The window keeps its size here. Backend scales the stored rectangle with the zoom, so a
        plaque the user sized keeps its proportions.
        """
        scale = plaque_scale(float(setting))
        if scale == self._scale:
            return
        self._scale = scale
        self._push()

    def size_key(self):
        """The old step nearest the size drawn, for a page that only knows those."""
        return min(self.OLD_FACTORS, key=lambda k: abs(self.OLD_FACTORS[k] - self._scale))

    def set_pinned(self, pinned) -> None:
        """A pinned plaque is click-through, except for the unpin button under the cursor."""
        self._pinned = bool(pinned)
        self._hot = False
        self._refresh_input()
        self._push()

    def set_opacity(self, value) -> None:
        super().set_opacity(value)
        self._push()

    def has_steps(self):
        return any(s[0] > self._done for s in self._steps)

    def default_region(self) -> Region:
        """Where a plaque that was never placed appears, at the zoom set."""
        return {
            "left": 60,
            "top": 140,
            "width": round(self.BASE_WIDTH * self._scale),
            "height": round(self.BASE_HEIGHT * self._scale),
        }

    def data_json(self):
        return json.dumps(
            {
                "steps": [
                    {
                        "n": n,
                        "text": t,
                        "color": c,
                        **({"icon": icon} if icon else {}),
                        **({"object": on} if on else {}),
                    }
                    for n, t, c, icon, on in self._steps
                ],
                "done": self._done,
                "past": self._past,
                "title": self._title,
                "size": self.size_key(),
                "scale": self._scale,
                "pinned": self._pinned,
                "grip": self.GRIP,  # api 18: the resize strips along the right and bottom edges
                # the step arrows: always offered, since progress always counts (api 16)
                "switch": True,
                "opacity": self._opacity,
                # The plaque is its own document and never sees getState, so the language it
                # should render in has to travel with its data.
                "language": current_language(),
            },
            ensure_ascii=False,
        )

    def _push(self) -> None:
        self._bridge.dataChanged.emit(self.data_json())

    def set_hotspot(self, rect) -> None:
        self._hotspot = rect
        self._sync_hot_timer()

    def _sync_hot_timer(self) -> None:
        watch = self._pinned and self.isVisible() and not self._hotspot.isNull()
        if watch and not self._hot_timer.isActive():
            self._hot_timer.start()
        elif not watch and self._hot_timer.isActive():
            self._hot_timer.stop()

    def _check_hotspot(self) -> None:
        # A click-through window receives no mouse events at all, so the unpin button cannot
        # be hovered the usual way: the cursor is polled against the hotspot instead, and
        # input transparency is lifted for as long as it sits inside.
        hot = self._hotspot.contains(self.mapFromGlobal(QCursor.pos()))
        if hot != self._hot:
            self._hot = hot
            self._refresh_input()

    def _refresh_input(self) -> None:
        self.set_click_through(self._pinned and not self._hot)
        self._sync_hot_timer()

    def begin_drag(self) -> None:
        """The page saw a press on the plaque's body: the window follows the mouse from there.

        The offset is taken from the press itself rather than from where the cursor is by the
        time the page's call arrives, so the plaque does not jump under the cursor.
        """
        origin = self._pressed_at if self._pressed_at is not None else QCursor.pos()
        self._grab = origin - self.frameGeometry().topLeft()

    def end_drag(self) -> None:
        if self._grab is None:
            return
        self._grab = None
        # Emitted once, at the end of the gesture, rather than on every move: the region is
        # persisted when the user lets go.
        self.regionChanged.emit(self.region_dict())

    def eventFilter(self, watched, event) -> bool:  # noqa: ARG002 -- Qt's signature
        """The mouse as the window receives it, before the page does.

        A press on the right or bottom edge of a loose plaque starts sizing it and never reaches
        the page. A drag the page started moves the window here. Both end on the release, or on
        a move with the button already up, should the release have gone astray.
        """
        kind = event.type()
        if not isinstance(event, QMouseEvent) or kind not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            return False
        at = event.globalPosition().toPoint()
        held = bool(event.buttons() & Qt.MouseButton.LeftButton)
        if kind == QEvent.Type.MouseButtonPress:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            self._pressed_at = at
            edges = "" if self._pinned else self.edges_at(event.position().toPoint())
            if edges:
                self._sizing = (edges, at, self.size())
                return True
            return False
        if self._sizing is not None:
            if kind == QEvent.Type.MouseMove and held:
                self._size_to(at)
            else:
                self._end_sizing()
            return True
        if self._grab is not None:
            if kind == QEvent.Type.MouseMove and held:
                self.move(at - self._grab)
            else:
                self.end_drag()
        return False

    def edges_at(self, point) -> str:
        """Which resize strip a window-local point is on: "r", "b", "rb" or none.

        The corner is a square twice the strips' width, as the page draws it, easier to hit.
        """
        x, y = point.x(), point.y()
        w, h = self.width(), self.height()
        if x >= w - 2 * self.GRIP and y >= h - 2 * self.GRIP:
            return "rb"
        return "r" if x >= w - self.GRIP else "b" if y >= h - self.GRIP else ""

    def _size_to(self, at) -> None:
        if self._sizing is None:
            return
        edges, origin, start = self._sizing
        width = start.width() + (at.x() - origin.x() if "r" in edges else 0)
        height = start.height() + (at.y() - origin.y() if "b" in edges else 0)
        self.resize(*self._clamp_size(width, height))

    def _end_sizing(self) -> None:
        self._sizing = None
        self.regionChanged.emit(self.region_dict())

    def set_region(self, region) -> None:
        """Move and size the plaque to the stored rectangle, kept within the screen.

        Ignored in the middle of a gesture: the progress path sets the stored rectangle several
        times a second, and would pull the window back to where the gesture began.
        """
        if self._grab is not None or self._sizing is not None:
            return
        width, height = self._clamp_size(int(region["width"]), int(region["height"]))
        self.setGeometry(int(region["left"]), int(region["top"]), width, height)

    def region_dict(self) -> Region:
        g = self.geometry()
        return {"left": g.x(), "top": g.y(), "width": g.width(), "height": g.height()}

    def _clamp_size(self, width, height) -> tuple[int, int]:
        """No smaller than the head and a row at the zoom set, no larger than the screen."""
        screen = self.screen() or QApplication.primaryScreen()
        room = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        least_w = round(self.MIN_WIDTH * self._scale)
        least_h = round(self.MIN_HEIGHT * self._scale)
        return (
            max(least_w, min(int(width), room.width())),
            max(least_h, min(int(height), room.height())),
        )

    def resizeEvent(self, event) -> None:
        self.view.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # The mouse is watched on the QWindow, which sees every event before the page's widgets
        # do. It exists from the first show and lasts as long as the widget.
        handle = self.windowHandle()
        if handle is not None and handle is not self._watched:
            handle.installEventFilter(self)
            self._watched = handle
        self._sync_hot_timer()

    def hideEvent(self, event) -> None:
        self._hot_timer.stop()
        self._grab = None
        self._sizing = None
        super().hideEvent(event)

    def retitle(self) -> None:
        """Re-read the title, and tell the page which language it is drawing in now.

        The plaque renders its own text, so a language change has to reach the page as
        data; it never sees getState.
        """
        self.setWindowTitle(t("native.window.steps"))
        self._push()
