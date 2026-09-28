"""Python's cyclic garbage collector, run on the GUI thread only.

Left to itself the collector runs on whichever thread's allocation crosses the threshold, and
the threads that allocate most are the vision workers: one detection makes thousands of match
objects. A collection there frees every unreachable cycle in the process, Qt wrappers made on
the GUI thread included, and a Qt object destroyed off its own thread while the GUI thread is
using Qt is an access violation. crash.log showed one: "Garbage-collecting" on the detector
thread in Tracker._knn while the GUI thread was painting the overlay.

So automatic collection is off, and a timer on the GUI thread runs the same generational
schedule the interpreter would. Reference counting still frees everything that is not in a
cycle at once, on whatever thread drops it; only cycles wait for the next tick.
"""

import gc
import time

from PySide6.QtCore import QObject, QTimer

# How often the young generation is looked at. Between ticks the workers pile up tens of
# thousands of objects at most, which a young collection gets through in a millisecond or two.
TICK_MS = 500
# A full collection walks every object in the process: a few milliseconds per hundred thousand,
# which the GUI thread can spare this rarely.
FULL_INTERVAL_S = 60.0


class GuiCollector(QObject):
    """Turns automatic collection off and runs it from a timer on the thread that owns this.

    Build it on the GUI thread, before any worker starts, and keep it alive as long as the
    application runs. `stop` turns automatic collection back on.
    """

    def __init__(self, parent: QObject | None = None, tick_ms: int = TICK_MS) -> None:
        super().__init__(parent)
        self._last_full = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(tick_ms)
        self._timer.timeout.connect(self.tick)
        gc.disable()
        self._timer.start()

    def tick(self) -> None:
        young, middle, _ = gc.get_count()
        young_limit, middle_limit, _ = gc.get_threshold()
        if young < young_limit:
            return
        if middle < middle_limit:
            gc.collect(0)
        elif time.monotonic() - self._last_full < FULL_INTERVAL_S:
            gc.collect(1)
        else:
            gc.collect()
            self._last_full = time.monotonic()

    def stop(self) -> None:
        self._timer.stop()
        gc.enable()
