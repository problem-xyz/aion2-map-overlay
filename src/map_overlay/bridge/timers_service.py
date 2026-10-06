"""The timers behind Backend: their data, the user's choices for them, what the pages see, and
the reminders.

Backend's timers slots are one call each into this service. It keeps the data fresh through
TimersDataService, writes the user's choices through the settings store like any preference, and
works out getState()["timers"] (timers/view.py). Pages count the seconds themselves, so the view
is only worked out again on a short tick and sent when what it says has changed: an event
starting or ending, a boss spawning, a choice made, newer data arriving.

Reminders wake a single-shot timer at exactly the next one due. When it fires, everything due
since the last look sounds once -- except what is long past, which is what a machine waking from
sleep would otherwise play as a pile. With the sound off, the plaque is asked to show itself
instead (`peek`), and either way `reminded` names the event, for the plaque to mark it.
"""

import dataclasses
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from map_overlay.bridge.timers_data import TimersDataService
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Settings
from map_overlay.store.timers import TimedEvent, WorldBoss
from map_overlay.timers.data import TimersData, TimersStore
from map_overlay.timers.reminders import Reminder, reminders_between, sound_for
from map_overlay.timers.sound import SoundPlayer
from map_overlay.timers.view import choice, ms, timers_view

log = logging.getLogger(__name__)

TICK_MS = 15_000
# The world bosses are off, at the owner's word: their list is still read and published, but the
# app neither shows them nor reminds of them. True brings back the lists, the plaque's rows, the
# timeline's lanes, the choice of bosses in Settings and their reminders, all at once.
WORLD_BOSSES = False
# Looked this far ahead for the next reminder; with none in it, looked again after RECHECK_MS.
LOOKAHEAD = timedelta(hours=2)
RECHECK_MS = 10 * 60 * 1000
# A reminder found later than this past its moment -- the machine slept through it -- is dropped.
STALE = timedelta(seconds=60)


def local_offset() -> timedelta:
    """How far this machine's clock is from UTC right now, summer time included."""
    return datetime.now().astimezone().utcoffset() or timedelta(0)


class TimersService(QObject):
    """GUI thread only. `changed` carries getState()["timers"] as JSON."""

    changed = Signal(str)
    reminded = Signal(str)  # JSON {"id", "name", "start", "boss"}: a reminder fell due
    peek = Signal()  # with the sound off, a reminder asks the plaque to show itself

    def __init__(
        self,
        dirs: DataDirs,
        *,
        settings: Callable[[], Settings],
        update_settings: Callable[[dict[str, Any]], None],
        notify: Callable[[str, str], None],
        data: TimersDataService | None = None,
        player: SoundPlayer | None = None,
        clock: Callable[[], datetime] | None = None,
        world_bosses: bool | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._world_bosses = WORLD_BOSSES if world_bosses is None else world_bosses
        self._settings = settings
        self._update_settings = update_settings
        self._data = data if data is not None else TimersDataService(TimersStore(dirs.cache))
        self._data.setParent(self)
        self._data.changed.connect(lambda _data: self._data_changed())
        self._data.failed.connect(lambda code: notify("warning", code))
        self._last = ""
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._emit)
        self._player = player or SoundPlayer()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._looked = self._clock()
        self._sounded: set[tuple[str, datetime]] = set()
        self._remind = QTimer(self)
        self._remind.setSingleShot(True)
        self._remind.timeout.connect(self._on_due)

    def start(self) -> None:
        self._data.set_enabled(self._settings().timers_fetch)
        self._data.start()
        self._tick.start()
        self._looked = self._clock()
        self._schedule_reminder()

    def close(self) -> None:
        self._tick.stop()
        self._remind.stop()
        self._data.close()

    @property
    def _in_use(self) -> TimersData:
        """The data as the app uses it: without the world bosses while they are off."""
        data = self._data.data
        return data if self._world_bosses else dataclasses.replace(data, bosses=None)

    def view(self, now: datetime | None = None) -> dict[str, Any] | None:
        return timers_view(
            self._in_use,
            self._settings(),
            now or self._clock(),
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
            self._schedule_reminder()

    def preview(self, event_id: str) -> None:
        """Play what the event's reminder sounds like, at the volume set; "" plays the chime.

        Whatever timers_sound says: this is the button that tries the sound out.
        """
        settings = self._settings()
        now = self._clock()
        reminder = None
        event = self._event(event_id)
        boss = self._boss(event_id)
        if event is not None:
            picked = choice(settings, event)
            lead = int(picked["lead"]) or 5
            reminder = Reminder(event.id, event.name, now, now, lead, picked["signal"])
        elif boss is not None:
            lead = settings.timers_world_lead or 5
            signal = "voice" if settings.timers_world_signal == "voice" else "chime"
            reminder = Reminder(boss.id, boss.name, now, now, lead, signal, boss=True)
        self._player.play(sound_for(reminder), settings.timers_volume)

    def _event(self, event_id: str) -> TimedEvent | None:
        schedule = self._in_use.schedule
        return next((e for e in schedule.events if e.id == event_id), None) if schedule else None

    def _boss(self, boss_id: str) -> WorldBoss | None:
        bosses = self._in_use.bosses
        return next((b for b in bosses.bosses if b.id == boss_id), None) if bosses else None

    def _schedule_reminder(self) -> None:
        now = self._clock()
        ahead = reminders_between(
            self._in_use, self._settings(), local_offset(), now, now + LOOKAHEAD
        )
        delay = RECHECK_MS
        if ahead:
            delay = max(250, int((ahead[0].at - now).total_seconds() * 1000) + 50)
        self._remind.start(delay)

    def _on_due(self) -> None:
        now = self._clock()
        settings = self._settings()
        due = reminders_between(self._in_use, settings, local_offset(), self._looked, now)
        self._looked = now
        for reminder in due:
            if reminder.key in self._sounded or now - reminder.at > STALE:
                continue
            self._sounded.add(reminder.key)
            log.info("reminder: %s at %s", reminder.name, reminder.start.isoformat())
            if settings.timers_sound:
                self._player.play(sound_for(reminder), settings.timers_volume)
            else:
                self.peek.emit()
            payload = {
                "id": reminder.event_id,
                "name": reminder.name,
                "start": ms(reminder.start),
                "boss": reminder.boss,
            }
            self.reminded.emit(json.dumps(payload, ensure_ascii=False))
        # what has started is never due again
        self._sounded = {k for k in self._sounded if k[1] > now}
        self._schedule_reminder()

    def _data_changed(self) -> None:
        self._emit(force=True)
        self._schedule_reminder()

    def _emit(self, *, force: bool = False) -> None:
        view = self.view()
        # "now" changes on every tick; whether anything else did is what decides a send
        key = json.dumps({k: v for k, v in (view or {}).items() if k != "now"}, sort_keys=True)
        if not force and key == self._last:
            return
        self._last = key
        self.changed.emit(json.dumps(view, ensure_ascii=False))
