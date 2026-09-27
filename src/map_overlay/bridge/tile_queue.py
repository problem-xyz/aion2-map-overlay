"""Building map tile pyramids off the GUI thread."""

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from map_overlay.core.constants import TILES_SHUTDOWN_WAIT_MS
from map_overlay.core.errors import MapError
from map_overlay.store import maps, tiles

log = logging.getLogger(__name__)

ReferenceOf = Callable[[str], Path | None]


class TileWorker(QThread):
    """Cuts maps into tile pyramids in the background.

    Cutting one inline freezes the interface for several seconds, which is the whole reason
    this is a thread. run() belongs to the worker and touches only the store; every other
    method is called from the GUI thread. request_stop() is checked between maps and inside
    build_tiles, so shutdown does not have to sit through a whole map.
    """

    mapDone = Signal(str, bool)

    def __init__(self, dirs, jobs: list[tuple[str, Path | None]], parent=None) -> None:
        super().__init__(parent)
        self.dirs = dirs
        self.jobs = list(jobs)
        self._stop = False

    def request_stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        for map_id, reference in self.jobs:
            if self._stop:
                return
            ok = True
            try:
                if reference is None:
                    raise MapError("map.unknown", id=map_id)
                info = tiles.build_tiles(
                    maps.map_dir(self.dirs, map_id), reference, should_stop=lambda: self._stop
                )
                ok = info is not None
            except Exception:
                log.exception("tiles for map %r failed", map_id)
                ok = False
            if not self._stop:
                self.mapDone.emit(map_id, ok)


class TileBuildQueue(QObject):
    """Serialises tile builds so that two maps never fight for the disk.

    A map queued while another is being cut waits its turn rather than starting a second
    worker. Finished workers are dropped through deleteLater from a slot, never from inside
    their own signal emission. `reference_of` answers where a map's image is; the worker is
    handed the path rather than the registry, so the store it touches stays plain files.
    """

    mapDone = Signal(str, bool)

    def __init__(self, dirs, reference_of: ReferenceOf, parent=None) -> None:
        super().__init__(parent)
        self._dirs = dirs
        self._reference_of = reference_of
        self._worker = None
        self._building_map_ids = []

    def enqueue(self, map_ids) -> None:
        for map_id in map_ids:
            if map_id not in self._building_map_ids:
                self._building_map_ids.append(map_id)
        self._pump()

    def is_busy(self, map_id):
        return map_id in self._building_map_ids

    def busy(self):
        """Map ids queued or being cut right now. A copy: the UI must not hold our list."""
        return list(self._building_map_ids)

    def _pump(self) -> None:
        if not self._building_map_ids or (self._worker and self._worker.isRunning()):
            return
        jobs = [(map_id, self._reference_of(map_id)) for map_id in self._building_map_ids]
        self._worker = TileWorker(self._dirs, jobs, self)
        self._worker.mapDone.connect(self._on_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, map_id, ok) -> None:
        if map_id in self._building_map_ids:
            self._building_map_ids.remove(map_id)
        self.mapDone.emit(map_id, ok)

    def _on_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()
        self._pump()

    def shutdown(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(TILES_SHUTDOWN_WAIT_MS)
        self._building_map_ids.clear()
