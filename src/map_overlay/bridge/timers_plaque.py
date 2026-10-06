"""The timers plaque behind Backend: when it is up, where, and what it shows.

The window is built the first time it is shown, not with the app: most players may never put it
up, and a QWebEngineView is not free. Everything it needs arrives from here -- the timers from
TimersService, the plaque's own settings and state from the store -- and what the user does on it
goes back the same way: a pin or a fold is a setting, a move is state, a close hides it.
"""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject

from map_overlay.core.settings import Settings, State
from map_overlay.qt.timers_window import TimersPlaqueWindow

log = logging.getLogger(__name__)

PLAQUE_SETTINGS = (
    "timers_plaque_pinned",
    "timers_plaque_scale",
    "timers_plaque_filter",
    "timers_plaque_collapsed",
    "timers_clock_12h",
    "timers_world_lead",
    "opacity",
)


class TimersPlaque(QObject):
    """GUI thread only. `changed` is Backend's to send state on: the plaque came up or went."""

    def __init__(
        self,
        *,
        dev: bool,
        settings: Callable[[], Settings],
        state: Callable[[], State],
        set_state: Callable[..., Any],
        change_settings: Callable[[dict[str, Any]], None],
        recordable: Callable[[], bool],
        on_visibility: Callable[[], None],
        display_scale: float = 1.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._dev = dev
        self._settings = settings
        self._state = state
        self._set_state = set_state
        self._change_settings = change_settings
        self._recordable = recordable
        self._on_visibility = on_visibility
        # Qt's own HiDPI scaling is off, so every window works in physical pixels: on a 4K screen
        # at 150% the plaque has to be drawn half as large again, or it comes up tiny.
        self._display_scale = display_scale
        self._window: TimersPlaqueWindow | None = None
        self._timers = ""

    @property
    def window(self) -> TimersPlaqueWindow | None:
        return self._window

    @property
    def visible(self) -> bool:
        return bool(self._window and self._window.isVisible() and not self._window.peeking)

    def _ensure(self) -> TimersPlaqueWindow:
        if self._window is None:
            window = TimersPlaqueWindow(self._dev)
            window.regionChanged.connect(self._on_moved)
            window.actionClicked.connect(self._on_action)
            self._window = window
            self._apply_prefs()
            window.set_pinned(self._settings().timers_plaque_pinned)
            window.set_recordable(self._recordable())
            if self._timers:
                window.set_timers(self._timers)
        return self._window

    def sync(self) -> None:
        """Show or hide the plaque as state.timers_plaque_visible says."""
        if not self._state().timers_plaque_visible:
            if self._window is not None and not self._window.peeking:
                self._window.hide()
            return
        window = self._ensure()
        window.set_region(self._state().timers_plaque_region or window.default_region())
        window.set_collapsed(self._settings().timers_plaque_collapsed)
        window.set_opacity(self._settings().opacity)
        window.show()
        window.apply_capture_mode()

    def set_visible(self, visible: bool) -> None:
        self._set_state(timers_plaque_visible=bool(visible))
        self.sync()
        self._on_visibility()

    def set_timers(self, payload: str) -> None:
        self._timers = payload
        if self._window is not None:
            self._window.set_timers(payload)

    def reminded(self, payload: str) -> None:
        if self._window is not None:
            self._window.ring(payload)

    def peek(self) -> None:
        """A reminder with the sound off: the plaque shows itself for a moment if it is hidden."""
        window = self._ensure()
        if not window.isVisible():
            window.set_region(self._state().timers_plaque_region or window.default_region())
            window.set_collapsed(self._settings().timers_plaque_collapsed)
            window.peek()

    def settings_changed(self, before: Settings, after: Settings) -> None:
        if self._window is None:
            return
        if any(getattr(before, k) != getattr(after, k) for k in PLAQUE_SETTINGS):
            if before.timers_plaque_scale != after.timers_plaque_scale:
                self._resize_by(after.timers_plaque_scale / before.timers_plaque_scale)
            self._apply_prefs()
            self._window.set_opacity(after.opacity)
            self._window.set_pinned(after.timers_plaque_pinned)
            self._window.set_collapsed(after.timers_plaque_collapsed)

    def set_recordable(self, recordable: bool) -> None:
        if self._window is not None:
            self._window.set_recordable(recordable)

    def retitle(self) -> None:
        if self._window is not None:
            self._window.retitle()

    def hide(self) -> None:
        if self._window is not None:
            self._window.hide()

    def shutdown(self) -> None:
        # Deleted with its page and the object on its channel, as the steps plaque is
        if self._window is not None:
            window, self._window = self._window, None
            window.close()
            window.deleteLater()

    def _apply_prefs(self) -> None:
        if self._window is None:
            return
        s = self._settings()
        self._window.set_prefs(
            filter_=s.timers_plaque_filter,
            clock_12h=s.timers_clock_12h,
            world_lead=s.timers_world_lead,
            scale=s.timers_plaque_scale * self._display_scale,
        )

    def _resize_by(self, ratio: float) -> None:
        """The size slider moved: the window grows with what it draws, as the steps plaque does."""
        if self._window is None:
            return
        g = self._window.geometry()
        self._window.resize(round(g.width() * ratio), round(g.height() * ratio))
        self._set_state(timers_plaque_region=self._window.region_dict())

    def _on_moved(self, region: dict[str, int]) -> None:
        self._set_state(timers_plaque_region=region)

    def _on_action(self, name: str) -> None:
        s = self._settings()
        if name == "close":
            self.set_visible(False)
        elif name == "pin":
            self._change_settings({"timers_plaque_pinned": not s.timers_plaque_pinned})
        elif name == "collapse":
            self._change_settings({"timers_plaque_collapsed": not s.timers_plaque_collapsed})
        elif name.startswith("filter:"):
            self._change_settings({"timers_plaque_filter": name.removeprefix("filter:")})
        else:
            log.warning("timers plaque: unknown action %r", name)
