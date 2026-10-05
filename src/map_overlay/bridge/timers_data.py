"""Keeps the timers' data fresh: a fetch soon after start, then every few hours, or on request.

The fetch runs on a daemon thread, as the updater's calls do (updater/worker.py says why not a
QThread), and its outcome comes back to the GUI thread through a queued signal. A fetch that
fails leaves the data in use as it was: a background check stays quiet about it, and only one
the user asked for reports a code.
"""

import contextlib
import gc
import logging
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from map_overlay.store.timers import TimersError
from map_overlay.timers.data import FILES, FetchError, TimersData, TimersStore, Transport
from map_overlay.timers.data import http_transport as default_transport

log = logging.getLogger(__name__)

FIRST_CHECK_DELAY_MS = 15_000
CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000


@dataclass(frozen=True)
class _Outcome:
    taken: bool  # a newer copy of either file came in
    error: str | None  # the first failure, for the log
    manual: bool


class _Relay(QObject):
    """Emitted on the fetch thread, delivered on the thread the service lives on."""

    done = Signal(object)  # _Outcome


class TimersDataService(QObject):
    """The data in use, and the fetches that replace it. GUI thread, apart from the fetch."""

    changed = Signal(object)  # TimersData, after a fetch took in a newer copy
    failed = Signal(str)  # a notify code, for a fetch the user asked for

    def __init__(
        self,
        store: TimersStore,
        transport: Transport = default_transport,
        first_check_ms: int = FIRST_CHECK_DELAY_MS,
        interval_ms: int = CHECK_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._transport = transport
        self._data = store.current()
        self._enabled = True
        self._thread: threading.Thread | None = None
        self._first_check_ms = first_check_ms
        self._relay = _Relay(self)
        self._relay.done.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(lambda: self.refresh(manual=False))

    @property
    def data(self) -> TimersData:
        return self._data

    @property
    def busy(self) -> bool:
        return self._thread is not None

    def start(self) -> None:
        """Schedule the first check and the regular ones, if fetching is on."""
        if self._enabled:
            QTimer.singleShot(self._first_check_ms, self, lambda: self.refresh(manual=False))
            self._timer.start()

    def set_enabled(self, enabled: bool) -> None:
        """Fetching off: no checks at all, and the copies already held stay in use."""
        self._enabled = bool(enabled)
        if not self._enabled:
            self._timer.stop()
        elif not self._timer.isActive():
            self._timer.start()

    def refresh(self, *, manual: bool = True) -> bool:
        """Start a fetch of both files; False when one is already running or fetching is off."""
        if self._thread is not None or not (self._enabled or manual):
            return False
        # Collect here, on the GUI thread: an allocation on the fetch thread could otherwise
        # start a collection there and free a Qt object off its own thread.
        gc.collect()
        self._thread = threading.Thread(
            target=self._work, args=(manual,), name="timers-fetch", daemon=True
        )
        self._thread.start()
        return True

    def close(self) -> None:
        """Stop the checks. A fetch still running is left to end with the process."""
        self._timer.stop()

    def _work(self, manual: bool) -> None:
        """Fetch thread. Touches the store's files and the relay, nothing of Qt's widgets."""
        taken, error = False, None
        for kind in FILES:
            try:
                taken = self._store.refresh(kind, self._transport) or taken
            except (FetchError, TimersError) as e:
                log.warning("timers %s not fetched: %s", kind, e)
                error = error or str(e)
            except OSError as e:
                log.exception("timers %s could not be stored", kind)
                error = error or str(e)
        with contextlib.suppress(RuntimeError):
            self._relay.done.emit(_Outcome(taken, error, manual))

    @Slot(object)
    def _deliver(self, outcome: _Outcome) -> None:
        self._thread = None
        if outcome.taken:
            self._data = self._store.current()
            self.changed.emit(self._data)
        if outcome.error and outcome.manual:
            self.failed.emit("timers.fetch_failed")
