"""Tells the app that a folder's files changed, once the changes have stopped coming."""

import logging
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

log = logging.getLogger(__name__)

# One atomic save is three notifications, and a copy of several files is one per file: they
# are answered once, after the folder has been quiet this long.
FOLDER_SETTLE_MS = 300


class FolderWatcher(QObject):
    """Emits `changed` after a file in `path` is added, removed, renamed or rewritten.

    The OS pushes the notifications, so a folder nobody touches costs nothing. A folder that is
    deleted drops out of the watch for the rest of the run. GUI thread only; close() it on
    shutdown, so that a change landing during the exit is not answered.
    """

    changed = Signal()

    def __init__(
        self, path: Path, parent: QObject | None = None, settle_ms: int = FOLDER_SETTLE_MS
    ) -> None:
        super().__init__(parent)
        self._closed = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(settle_ms)
        self._timer.timeout.connect(self._fire)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._schedule)
        if not self._watcher.addPath(str(path)):
            log.warning("changes in %s will not be noticed", path)

    def close(self) -> None:
        self._closed = True
        self._timer.stop()

    def _schedule(self, *_args: object) -> None:
        if not self._closed:
            self._timer.start()

    def _fire(self) -> None:
        if not self._closed:
            self.changed.emit()
