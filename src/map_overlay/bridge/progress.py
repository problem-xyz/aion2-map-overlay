"""How far along a route the player is, and when to tick the next point off.

Kept apart from the windows on purpose: the arrival test is the only part of this that is
worth testing, and it is pure arithmetic over the route document once the caller has converted
the player's position into route coordinates.
"""

import bisect
import logging
import math

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)

# How far off the leg being walked the player has to be before the overlay says so, as a share of
# the map's width, and how near to come back for it to stop saying it. Both maps are 4096 wide:
# 160 and 120 map pixels, several arrival rings away. Two numbers, so that a player on the edge
# does not make the strip blink.
FAR_FROM_ROUTE = 160 / 4096
BACK_ON_ROUTE = 120 / 4096

# The eight points of the compass, clockwise from north, as the catalogue names them.
COMPASS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")


def _to_segment(px, py, a, b) -> float:
    ax, ay, bx, by = a["x"], a["y"], b["x"], b["y"]
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    k = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(ax + k * dx - px, ay + k * dy - py)


def compass(dx, dy) -> str:
    """Which way (dx, dy) points, map y growing south, as one of COMPASS."""
    angle = math.degrees(math.atan2(dx, -dy)) % 360  # 0 is north, 90 east
    return COMPASS[round(angle / 45) % 8]


def _in_route_pixels(x, y, doc, ref_size):
    """The player's position in the route's coordinates, and the map's width there; or None."""
    if not (doc and doc["markers"] and ref_size):
        return None
    mw, mh = doc["mapSize"]
    rw, rh = ref_size
    if min(mw, mh, rw, rh) <= 0:
        return None
    return x * mw / rw, y * mh / rh, mw


def rejoin_at(x, y, doc, done, ref_size, *, radius):
    """The first point past the next one the player stands at, by index, or None.

    For a player who lost the route: they may have walked on to a later point, and the route
    can go on from there. The first such point, not the furthest: a route that comes back to a
    spot -- a teleport -- would otherwise skip the whole loop between. `radius` is the arrival
    radius as a share of the map's width.
    """
    where = _in_route_pixels(x, y, doc, ref_size)
    if where is None:
        return None
    px, py, mw = where
    reach = float(radius) * mw
    for i in range(done + 1, len(doc["markers"])):
        m = doc["markers"][i]
        if math.hypot(m["x"] - px, m["y"] - py) <= reach:
            return i
    return None


def off_route(x, y, doc, done, ref_size, *, was_off=False):
    """(index of the next point, the way to it) when the player is far off the route, else None.

    Far off means away from the leg being walked, from the last point passed to the next one,
    or from the first point before any is passed: walking that leg is on the route however long
    it is. Player position in reference pixels, as on_player takes it.
    """
    where = _in_route_pixels(x, y, doc, ref_size)
    if where is None or done >= len(doc["markers"]):
        return None
    px, py, mw = where
    markers = doc["markers"]
    target = markers[done]
    start = markers[done - 1] if done > 0 else target
    limit = (BACK_ON_ROUTE if was_off else FAR_FROM_ROUTE) * mw
    if _to_segment(px, py, start, target) <= limit:
        return None
    return done, compass(target["x"] - px, target["y"] - py)


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
        # The points of the whole route the player is shown, by index, when some are left out;
        # None when all are. The count is kept over the whole route either way, so that turning
        # the feathers back on finds the progress where it was.
        self._kept: list[int] | None = None
        self._whole = 0

    def set_view(self, kept, whole) -> None:
        """Count over the `kept` points of a route `whole` points long, or over all with None."""
        self._kept = None if kept is None else list(kept)
        self._whole = int(whole)

    @property
    def _progress(self):
        return self._store.state.progress

    def done_count(self, doc=None):
        """How many points of the open route are done, within its length when doc is given."""
        route = self._store.state.route
        done = int(self._progress.get(route, 0)) if route else 0
        if self._kept is not None:
            done = bisect.bisect_left(self._kept, done)  # the points shown before the next one
        if doc:
            done = min(done, len(doc["markers"]))
        return max(0, done)

    def set_done(self, done, doc):
        """Returns True when something actually changed."""
        route = self._store.state.route
        total = len(doc["markers"]) if doc else 0
        done = max(0, min(int(done), total))
        # The points left out before the next one shown count as passed with the one before it.
        kept = self._kept
        whole = done if kept is None else (kept[done] if done < len(kept) else self._whole)
        if not route or self._progress.get(route, 0) == whole:
            return False
        self._store.set_state(progress={**self._progress, route: whole})
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
