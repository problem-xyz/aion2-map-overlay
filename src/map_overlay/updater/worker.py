"""One Velopack call at a time, on a thread of its own, with the outcome queued back.

The threads are daemon threading.Threads, not QThreads. A Velopack call cannot be interrupted --
a delta download ends in an Update.exe patch run that took 11 s when measured -- and a QThread still
running when the app exits is destroyed while it runs, which Qt answers with qFatal: measured,
such a process ended with 0xC0000409 instead of 0. A daemon thread nobody waits for any more is
simply dropped at exit. join() is there for the one wait allowed, the one on the way out.
"""

import contextlib
import gc
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from map_overlay.updater.manager import NotInstalledError

log = logging.getLogger(__name__)


class Op(StrEnum):
    """The operations a worker runs; also the `stage` a failure names."""

    PROBE = "probe"
    CHECK = "check"
    DOWNLOAD = "download"
    INSTALL = "install"
    EXIT = "exit"


@dataclass(frozen=True)
class Outcome:
    """What a worker hands back: the operation, and its value or the first line of its error."""

    op: Op
    value: Any = None
    error: str | None = None
    unavailable: bool = False


def first_line(error: BaseException) -> str:
    text = str(error).strip()
    return text.splitlines()[0] if text else type(error).__name__


class _Relay(QObject):
    """Emitted on a worker thread, delivered on the thread the Worker lives on."""

    done = Signal(object)  # Outcome
    progress = Signal(int)


class Worker(QObject):
    """Runs one job at a time and reports on the thread it was made on, the GUI thread.

    `busy` stays true until the outcome has been delivered, not merely until the job returned,
    so a caller that reacts to `done` sees the worker free again.
    """

    done = Signal(object)  # Outcome
    progress = Signal(int)  # a percentage, from Velopack's download callback

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._op: Op | None = None
        self._thread: threading.Thread | None = None
        self._relay = _Relay(self)
        self._relay.done.connect(self._deliver, Qt.ConnectionType.QueuedConnection)
        self._relay.progress.connect(self.progress, Qt.ConnectionType.QueuedConnection)

    @property
    def busy(self) -> bool:
        return self._op is not None

    @property
    def op(self) -> Op | None:
        return self._op

    def run(self, op: Op, job: Callable[[], Any]) -> threading.Thread | None:
        """Start `job` on a new thread. None, and nothing started, while another one runs."""
        if self._op is not None:
            return None
        self._op = op
        # Collect here, on the GUI thread: otherwise an allocation on the worker can start a
        # collection there, and a Qt object freed off its own thread is a qFatal. Seen in CI as
        # 0x80000003 inside a fake UpdateManager's __init__ on "updater-probe".
        gc.collect()
        thread = threading.Thread(
            target=self._work, args=(op, job), name=f"updater-{op.value}", daemon=True
        )
        self._thread = thread
        thread.start()
        return thread

    def join(self, timeout_s: float) -> bool:
        """Wait for the running thread; True once none runs. On the way out only."""
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout_s)
            return not thread.is_alive()
        return True

    def release(self) -> None:
        """Forget a finished job whose outcome will not be delivered: the app is closing."""
        self._op = None

    def report(self, percent: int) -> None:
        """Worker thread: Velopack's progress callback, which swallows what it raises."""
        with contextlib.suppress(RuntimeError):
            self._relay.progress.emit(int(percent))

    def _work(self, op: Op, job: Callable[[], Any]) -> None:
        """Worker thread. Touches nothing but the relay."""
        try:
            outcome = Outcome(op, value=job())
        except NotInstalledError as e:
            log.info("updates are off for this copy: %s", e)
            outcome = Outcome(op, error=first_line(e), unavailable=True)
        except RuntimeError as e:
            # Velopack reports every failure -- network, timeout, a bad feed, IO -- this way.
            log.warning("update %s failed: %s", op.value, e)
            outcome = Outcome(op, error=first_line(e))
        except Exception as e:
            log.exception("update %s failed", op.value)
            outcome = Outcome(op, error=first_line(e))
        except BaseException as e:
            # A Rust panic comes back as pyo3's PanicException, which is not an Exception.
            # Without an outcome the worker would stay busy, and every later request be ignored.
            log.exception("update %s failed", op.value)
            outcome = Outcome(op, error=first_line(e))
        # The relay goes with the window at exit, possibly before a left-behind thread ends.
        with contextlib.suppress(RuntimeError):
            self._relay.done.emit(outcome)

    @Slot(object)
    def _deliver(self, outcome: Outcome) -> None:
        self._op = None
        self.done.emit(outcome)
