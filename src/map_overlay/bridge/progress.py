"""How far along a route the player is, and when to tick the next point off.

Kept apart from the windows on purpose: the arrival test is the only part of this that is
worth testing, and it is pure arithmetic over the route document once the caller has converted
the player's position into route coordinates.
"""

import logging
import math

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class ProgressTracker(QObject):
    """Owns the per-route done count: the only writer of `state.progress`.

    Counts are kept per route id and clamped to the route's length on every read as well as
    on write, because a route can be shortened in the editor between two runs.

    GUI thread only, and no window is touched from here -- a change is announced by `changed`.
    """

    changed = Signal(int, int)  # done, total

    def __init__(self, store, parent=None) -> None:
        super().__init__(parent)
        self._store = store

    @property
    def _progress(self):
        return self._store.state.progress

    def done_count(self, doc=None):
        """How many points of the open route are done, within its length when doc is given."""
        route = self._store.state.route
        done = int(self._progress.get(route, 0)) if route else 0
        if doc:
            done = min(done, len(doc["markers"]))
        return max(0, done)

    def set_done(self, done, doc):
        """Returns True when something actually changed."""
        route = self._store.state.route
        total = len(doc["markers"]) if doc else 0
        done = max(0, min(int(done), total))
        if not route or self._progress.get(route, 0) == done:
            return False
        self._store.set_state(progress={**self._progress, route: done})
        self.changed.emit(done, total)
        return True

    def clamp_to(self, route_id, total) -> None:
        """A route shortened in the editor must not leave progress pointing past its end."""
        if self._progress.get(route_id, 0) > total:
            self._store.set_state(progress={**self._progress, route_id: total})

    def forget(self, route_id) -> None:
        self._store.set_state(progress={k: v for k, v in self._progress.items() if k != route_id})

    def on_player(self, x, y, doc, ref_size):
        """Player position in reference pixels: has the next point been reached?

        Returns the new done count, or None if nothing changed.
        """
        settings = self._store.settings
        route = self._store.state.route
        if not settings.auto_progress:
            return None
        if not (route and doc and doc["markers"]):
            return None
        if not ref_size:
            return None
        mw, mh = doc["mapSize"]
        rw, rh = ref_size
        if min(mw, mh, rw, rh) <= 0:
            return None

        px, py = x * mw / rw, y * mh / rh  # reference pixels -> route coordinates
        done = self.done_count(doc)
        radius = float(settings.arrive_radius) * mw
        markers = doc["markers"]
        # Points are ticked off in their order and only in it: the next one, never one past it.
        # A lookahead of two let a run past point 3 close points 1 to 3 at once -- by a point
        # the overlay did not even show, or by the return visit to a teleport the player was
        # still standing on. A point skipped on purpose is ticked off by hand.
        if done >= len(markers):
            return None
        m = markers[done]
        return done + 1 if math.hypot(m["x"] - px, m["y"] - py) <= radius else None
