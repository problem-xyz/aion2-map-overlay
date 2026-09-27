"""Holds settings and state in memory and writes them out, debounced.

Dragging a slider or walking a route produces updates at the frame rate. Writing the file on
every one of them meant hundreds of writes a second against the user's disk, so a change marks
the file dirty and a single-shot timer does the write ~400 ms later. Settings and state have
separate timers and separate files: a progress tick must not rewrite preferences.

flush() exists because a debounced write that never happens is a lost setting. It runs on
shutdown, on aboutToQuit, and before an update is installed.
"""

import logging
from dataclasses import fields as dataclass_fields
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer

from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import (
    Settings,
    State,
    coerce,
    load,
    settings_payload,
    state_payload,
)

log = logging.getLogger(__name__)

WRITE_DELAY_MS = 400

# Carried through reset_settings(): the updater's own fields, which no control in the Settings
# block shows. The skipped version is the answer the user already gave to one update prompt,
# and clearing it would bring back a banner they dismissed. The two switches decide whether the
# app goes online at all, and a reset of the detection settings must not quietly turn network
# access back on for someone who turned it off.
KEPT_ON_RESET = ("updates_auto_check", "updates_auto_download", "updates_skipped_version")


class SettingsStore(QObject):
    """The only writer of settings.json and state.json, and the only gate onto their values.

    `settings` and `state` are read straight off this object, and both writes are debounced,
    so memory runs ahead of the disk until flush(). Anything that ends the process has to
    call flush() first or the last change is lost.

    update_settings() is the only way a preference changes, and it puts the patch through the
    same coercion the file on disk goes through, so no caller -- the UI least of all -- can
    store a key the schema does not know or a value outside its range. set_state() is the
    counterpart for machine state: it takes field names on State and coerces the same way.

    GUI thread only: the debounce is a QTimer parented here.
    """

    def __init__(self, dirs: DataDirs, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dirs = dirs

        result = load(dirs.settings, dirs.state)
        self.settings: Settings = result.settings
        self.state: State = result.state
        self.reset_keys = result.reset_keys
        self.corrupt_backup = result.corrupt_backup

        self._settings_dirty = False
        self._state_dirty = False
        self._settings_timer = self._make_timer(self._write_settings)
        self._state_timer = self._make_timer(self._write_state)

        if result.migrated or result.reset_keys or result.corrupt_backup:
            # Persist the repair straight away. A migration must not be lost to a crash before
            # the first edit, and leaving rejected values on disk would show the user the same
            # "values were reset" toast on every single launch.
            self._write_settings()
            self._write_state()

    def _make_timer(self, slot) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(WRITE_DELAY_MS)
        timer.timeout.connect(slot)
        return timer

    # ------------------------------------------------------------------ settings
    def update_settings(self, patch: dict[str, Any]) -> Settings:
        """Apply a patch from the UI through the same validation the file goes through."""
        merged = {**settings_payload(self.settings), **(patch or {})}
        new, reset = coerce(merged, Settings)
        if reset:
            log.warning("update_settings: rejected values for %s", ", ".join(reset))
        if new != self.settings:
            self.settings = new
            self._settings_dirty = True
            self._settings_timer.start()
        return self.settings

    def reset_settings(self) -> Settings:
        """Every preference back to its default, except the fields in KEPT_ON_RESET.

        Goes through update_settings, so the write is the same debounced one any edit makes.
        State -- the map area, the plaque position, the open route and its progress -- is a
        separate file and is left alone.
        """
        kept = {name: getattr(self.settings, name) for name in KEPT_ON_RESET}
        return self.update_settings({**settings_payload(Settings()), **kept})

    # ------------------------------------------------------------------ state
    def set_state(self, **fields: Any) -> State:
        """Change state fields by name, through the same coercion the file goes through.

        Every caller passes values it computed itself, but a region from a screen geometry or
        a progress count is still a number that could be NaN; coercion keeps it off the disk
        and out of getState(), where the panel's JSON.parse would reject the whole state.
        """
        unknown = sorted(set(fields) - {f.name for f in dataclass_fields(State)})
        if unknown:
            raise TypeError(f"set_state: no State field {', '.join(unknown)}")
        new, reset = coerce({**state_payload(self.state), **fields}, State)
        if reset:
            log.warning("set_state: rejected values for %s", ", ".join(reset))
        if new != self.state:
            self.state = new
            self._state_dirty = True
            self._state_timer.start()
        return self.state

    # ------------------------------------------------------------------ writing
    def _write_settings(self) -> None:
        self._settings_dirty = False
        self._write(self._dirs.settings, settings_payload(self.settings))

    def _write_state(self) -> None:
        self._state_dirty = False
        self._write(self._dirs.state, state_payload(self.state))

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        # Coercion is what keeps NaN out; this is the check that it did. A file with NaN in it
        # would load (json.loads reads it) and then blank the panel, so it is not written.
        try:
            atomic_write_json(path, payload, allow_nan=False)
        except ValueError:
            log.exception("not writing %s: a value is NaN or infinite", path.name)

    def flush(self) -> None:
        """Write anything still pending, now. Safe to call more than once."""
        self._settings_timer.stop()
        self._state_timer.stop()
        if self._settings_dirty:
            self._write_settings()
        if self._state_dirty:
            self._write_state()
