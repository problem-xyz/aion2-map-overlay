"""The timers behind Backend: their data, the user's choices for them, and what the pages see.

Backend's timers slots are one call each into this service. It keeps the data fresh through
TimersDataService, writes the user's choices through the settings store like any preference, and
works out getState()["timers"] (timers/view.py). Pages count the seconds themselves, so the view
is only worked out again on a short tick and sent when what it says has changed: an event
starting or ending, a boss spawning, a choice made, newer data arriving.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from map_overlay.bridge.timers_data import TimersDataService
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Settings
from map_overlay.timers.data import TimersStore
from map_overlay.timers.view import timers_view

log = logging.getLogger(__name__)

TICK_MS = 15_000


def local_offset() -> timedelta:
    """How far this machine's clock is from UTC right now, summer time included."""
    return datetime.now().astimezone().utcoffset() or timedelta(0)


class TimersService(QObject):
    """GUI thread only. `changed` carries getState()["timers"] as JSON."""

    changed = Signal(str)

    def __init__(
        self,
        dirs: DataDirs,
        *,
        settings: Callable[[], Settings],
        update_settings: Callable[[dict[str, Any]], None],
        notify: Callable[[str, str], None],
        data: TimersDataService | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._update_settings = update_settings
        self._data = data if data is not None else TimersDataService(TimersStore(dirs.cache))
        self._data.setParent(self)
        self._data.changed.connect(lambda _data: self._emit(force=True))
        self._data.failed.connect(lambda code: notify("warning", code))
        self._last = ""
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._emit)

    def start(self) -> None:
        self._data.set_enabled(self._settings().timers_fetch)
        self._data.start()
        self._tick.start()

    def close(self) -> None:
        self._tick.stop()
        self._data.close()

    def view(self, now: datetime | None = None) -> dict[str, Any] | None:
        return timers_view(
            self._data.data,
            self._settings(),
            now or datetime.now(UTC),
            local_offset(),
            fetching=self._data.busy,
        )

    def set_event(self, event_id: str, patch: dict[str, Any]) -> None:
        """One event's choices, merged over what the user chose before; coercion checks them."""
        if not event_id:
            return
        events = dict(self._settings().timers_events)
        events[event_id] = {**events.get(event_id, {}), **patch}
        self._update_settings({"timers_events": events})

    def set_world_shown(self, ids: list[str]) -> None:
        self._update_settings({"timers_world_shown": ids})

    def refresh(self) -> None:
        """Fetch now, at the user's word; the view says it is fetching until it is done."""
        if self._data.refresh(manual=True):
            self._emit(force=True)

    def settings_changed(self, before: Settings, after: Settings) -> None:
        if before.timers_fetch != after.timers_fetch:
            self._data.set_enabled(after.timers_fetch)
        timers = [name for name in vars(after) if name.startswith("timers_")]
        if any(getattr(before, n) != getattr(after, n) for n in timers):
            self._emit(force=True)

    def _emit(self, *, force: bool = False) -> None:
        view = self.view()
        # "now" changes on every tick; whether anything else did is what decides a send
        key = json.dumps({k: v for k, v in (view or {}).items() if k != "now"}, sort_keys=True)
        if not force and key == self._last:
            return
        self._last = key
        self.changed.emit(json.dumps(view, ensure_ascii=False))
