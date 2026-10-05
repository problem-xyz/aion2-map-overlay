"""The timers plaque: a small always-on-top window with the events and bosses to come."""

import json
from typing import Any

from PySide6.QtCore import QTimer

from map_overlay.core.settings import Region
from map_overlay.i18n.catalog import current_language, t
from map_overlay.qt.plaque_window import PlaqueWindow


class TimersPlaqueWindow(PlaqueWindow):
    """The timers' plaque over the game, drawn by the page in its `#timers` mode.

    Everything native is PlaqueWindow's. This class holds what the page draws -- the timers as
    getState() carries them, the plaque's own choices, the reminder last sounded -- and the one
    thing a plaque of steps never does: folding up to its head, and showing itself for a moment
    when a reminder falls due with the sound off.

    The page talks to the `timers` object: getData, dragStart, dragEnd, action and setHotspot,
    with dataChanged. Actions are "pin", "collapse", "close" and "filter:<all|event|boss>".
    """

    BASE_WIDTH = 330
    BASE_HEIGHT = 320
    MIN_WIDTH = 220
    MIN_HEIGHT = 44  # the head alone, as when folded up
    COLLAPSED_HEIGHT = 44
    PEEK_MS = 8000  # how long a reminder shows a hidden plaque

    def __init__(self, dev: bool = False) -> None:
        self._timers: Any = None
        self._prefs: dict[str, Any] = {}
        self._ring: Any = None
        self._collapsed = False
        self._open_height: int | None = None  # the height to unfold to
        super().__init__(page="timers", channel_name="timers", dev=dev)
        self.setWindowTitle(t("native.window.timers"))
        self._peek = QTimer(self)
        self._peek.setSingleShot(True)
        self._peek.timeout.connect(self._end_peek)
        self._peeking = False

    def set_timers(self, payload: str) -> None:
        """getState()["timers"] as JSON, as timersChanged carries it."""
        self._timers = json.loads(payload) if payload else None
        self._push()

    def set_prefs(self, *, filter_: str, clock_12h: bool, world_lead: int, scale: float) -> None:
        self._prefs = {"filter": filter_, "clock12h": clock_12h, "worldLead": world_lead}
        self._scale = scale
        self._push()

    def ring(self, payload: str) -> None:
        """A reminder fell due: the page marks that row for a while."""
        self._ring = json.loads(payload) if payload else None
        self._push()

    def set_collapsed(self, collapsed: bool) -> None:
        """Fold the plaque to its head, or open it to the height it had."""
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        g = self.geometry()
        if collapsed:
            self._open_height = g.height()
            self.resize(g.width(), round(self.COLLAPSED_HEIGHT * self._scale))
        else:
            height = self._open_height or round(self.BASE_HEIGHT * self._scale)
            self.resize(g.width(), height)
        self._push()

    def region_dict(self) -> Region:
        """The rectangle to keep: while folded, with the height it unfolds to."""
        region = super().region_dict()
        if self._collapsed and self._open_height:
            region["height"] = self._open_height
        return region

    def set_region(self, region) -> None:
        super().set_region(region)
        if self._collapsed:
            self._open_height = int(region["height"])
            g = self.geometry()
            self.resize(g.width(), round(self.COLLAPSED_HEIGHT * self._scale))

    def peek(self) -> bool:
        """Show a hidden plaque for PEEK_MS; True if it was hidden and is now shown."""
        if self.isVisible():
            return False
        self._peeking = True
        self.show()
        self.apply_capture_mode()
        self._peek.start(self.PEEK_MS)
        return True

    @property
    def peeking(self) -> bool:
        return self._peeking

    def _end_peek(self) -> None:
        if self._peeking:
            self._peeking = False
            self.hide()

    def begin_drag(self) -> None:
        # a plaque the user takes hold of while it peeks stays where they put it
        self._peek.stop()
        self._peeking = False
        super().begin_drag()

    def data_json(self) -> str:
        return json.dumps(
            {
                "timers": self._timers,
                **self._prefs,
                "collapsed": self._collapsed,
                "ring": self._ring,
                "scale": self._scale,
                "pinned": self._pinned,
                "opacity": self._opacity,
                "grip": self.GRIP,
                "language": current_language(),
            },
            ensure_ascii=False,
        )

    def retitle(self) -> None:
        self.setWindowTitle(t("native.window.timers"))
        self._push()
