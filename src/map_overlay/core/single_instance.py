"""One running copy per user, with the second launch raising the first.

Two instances would fight over the same settings file, the same route progress and the same
capture region, and a user who double-clicks the shortcut twice has no way to tell which
window is the real one. So the second launch does the useful thing instead: it tells the first
to come forward, and exits.

A lock file alone is not enough -- it says "somebody is running" but gives no way to reach
them. The local socket is the channel; the lock is what makes the race safe.

The two are not ready at the same moment. A starting copy takes the lock before anything else
but listens only once its window is up, about a second later, and a double-click on the
shortcut lands in that gap. So silence is not taken for a crash straight away: the second
launch keeps trying for a while, and stops early if the lock comes free. Getting through is not
the end of it either. Qt's pipe has no buffer, so the request counts as delivered only once
the running copy has read it, which its event loop does only when start-up is over; a launch
that leaves before then takes the unread request with it. A copy that hangs up instead of
reading is shutting down, and the launch goes on waiting, for its lock this time.
"""

import logging
import time
from collections.abc import Callable
from enum import Enum

from PySide6.QtCore import QLockFile
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from map_overlay.core.appinfo import APP_DIR_NAME
from map_overlay.core.paths import DataDirs

log = logging.getLogger(__name__)

RAISE = b"raise\n"
CONNECT_TIMEOUT_MS = 500
LOCK_TIMEOUT_MS = 100
# How long a second launch waits for a lock holder that has not answered yet. Too short, and it
# starts beside a copy that was only slow to start. The wait is felt only when the holder never
# answers at all: a copy that is alive and not listening, or a crashed one whose pid another
# process of the same name has taken. A holder that is simply gone frees the lock at once.
ANSWER_WAIT_MS = 5000
RETRY_INTERVAL_S = 0.1


class Answer(Enum):
    """What came of asking the copy that holds the lock to come forward."""

    RAISED = "raised"  # it is running and has been asked: this launch has nothing left to do
    TOOK_OVER = "took over"  # it exited while we waited, and the lock is ours now
    SILENT = "silent"  # it held the lock throughout and never answered


class SingleInstance:
    """Holds the lock and the listening socket for the lifetime of the app."""

    def __init__(self, dirs: DataDirs, server_name: str | None = None) -> None:
        self._lock = QLockFile(str(dirs.root / "app.lock"))
        self._lock.setStaleLockTime(0)  # a crashed instance must not lock the app out forever
        self._name = server_name or f"{APP_DIR_NAME}-single-instance"
        self._server: QLocalServer | None = None
        self._on_raise = None

    def try_acquire(self) -> bool:
        """True if this process is the first one. False means another instance is running."""
        return self._lock.tryLock(LOCK_TIMEOUT_MS)

    def owner_pid(self) -> int | None:
        """The process id the running instance wrote into the lock, or None if unreadable."""
        pid, _host, _app = self._lock.getLockInfo()
        return pid or None

    def signal_existing(self, wait_ms: int = ANSWER_WAIT_MS) -> Answer:
        """Ask the running instance to show itself, waiting up to wait_ms for one still starting.

        If the lock comes free meanwhile, this instance takes it and answers TOOK_OVER. Needs
        no QCoreApplication, and blocks the calling thread while it waits -- holding the GIL,
        so it must run before a Python Qt message handler is installed (see
        core.logs.route_qt_messages).
        """
        deadline = time.monotonic() + wait_ms / 1000
        waited = False
        while True:
            socket = QLocalSocket()
            socket.connectToServer(self._name)
            if socket.waitForConnected(CONNECT_TIMEOUT_MS):
                socket.write(RAISE)
                remaining_ms = int((deadline - time.monotonic()) * 1000)
                if socket.waitForBytesWritten(max(remaining_ms, CONNECT_TIMEOUT_MS)):
                    socket.disconnectFromServer()
                    return Answer.RAISED
                if socket.state() == QLocalSocket.LocalSocketState.ConnectedState:
                    # Listening, so alive and this app: a second copy would still fight it.
                    log.warning("the running instance did not read the request in time")
                    return Answer.RAISED
                # It hung up without reading, which a copy on its way out does.
            if self._lock.tryLock(0):
                log.info("the instance that held the lock has exited; taking its place")
                return Answer.TOOK_OVER
            if time.monotonic() >= deadline:
                log.warning("another instance holds the lock but is not listening")
                return Answer.SILENT
            if not waited:
                log.info("another instance holds the lock but has not answered yet; waiting")
                waited = True
            time.sleep(RETRY_INTERVAL_S)

    def listen(self, on_raise: Callable[[], None]) -> None:
        """Start answering the other launches. on_raise runs on the GUI thread."""
        self._on_raise = on_raise
        # A previous crash can leave the name taken; nothing is listening on it, so it is ours.
        QLocalServer.removeServer(self._name)
        self._server = QLocalServer()
        if not self._server.listen(self._name):
            log.warning("cannot listen on %s: %s", self._name, self._server.errorString())
            self._server = None
            return
        self._server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        # Connected only to the server listen() kept, so there is one whenever this runs.
        socket = self._server.nextPendingConnection()  # pyright: ignore[reportOptionalMemberAccess]
        if socket is None:
            return
        socket.readyRead.connect(lambda: self._handle(socket))
        socket.disconnected.connect(socket.deleteLater)

    def _handle(self, socket: QLocalSocket) -> None:
        # QByteArray supports the buffer protocol; PySide6's stubs do not declare it.
        received = bytes(socket.readAll())  # pyright: ignore[reportArgumentType]
        if RAISE.strip() in received.strip() and self._on_raise:
            log.info("another launch asked us to come forward")
            self._on_raise()

    def release(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        self._lock.unlock()
