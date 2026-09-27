"""When the overlay window is on screen, through Backend, with only the engine thread stubbed.

The overlay follows the engine phase: it comes up with STARTING and goes with IDLE. A Start
pressed while the last run is still STOPPING is parked by EngineController and replayed after
that run's IDLE, so an overlay shown by start() itself was hidden by the IDLE that came next
and never shown again: a run with nothing drawn over the map, while the panel said it was on.
"""

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.engine_controller import Phase
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Region
from map_overlay.store import routes
from map_overlay.store.maps import MapSpec

REGION = Region(left=0, top=0, width=400, height=300)


@pytest.fixture
def backend(
    qapp: QApplication,
    dirs: DataDirs,
    bundled: tuple[MapSpec, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Backend]:
    """A Backend with a runnable route and a map area, whose engine thread never starts."""
    made = Backend(dirs)
    try:
        altgard = bundled[0]
        doc = routes.new_route_doc("map", altgard.id, list(altgard.size))
        routes.save_route(dirs, "route-map", doc)
        made.setRoute("route-map")
        made._store.set_state(region=REGION)
        monkeypatch.setattr(made, "_revalidate_screens", lambda: False)
        engine = made.engine._engine
        monkeypatch.setattr(engine, "start", lambda *a, **kw: True)
        monkeypatch.setattr(engine, "request_stop", lambda: None)
        yield made
    finally:
        made.shutdown()


def test_start_shows_the_overlay_and_stop_hides_it(backend: Backend) -> None:
    backend.start()
    assert (backend.engine.phase, backend.overlay.isVisible()) == (Phase.STARTING, True)
    backend.engine._engine.started_ok.emit("dxcam")
    assert (backend.engine.phase, backend.overlay.isVisible()) == (Phase.RUNNING, True)

    backend.stop()
    assert (backend.engine.phase, backend.overlay.isVisible()) == (Phase.STOPPING, False)


def test_a_start_parked_while_stopping_brings_the_overlay_back_with_its_run(
    backend: Backend,
) -> None:
    engine = backend.engine._engine
    backend.start()
    engine.started_ok.emit("dxcam")
    backend.stop()

    backend.start()  # the last run has not finished yet: remembered, not run
    assert backend.engine.phase is Phase.STOPPING
    assert not backend.overlay.isVisible()  # nothing is running under it yet

    engine.finished.emit()  # IDLE for the old run, then STARTING for the replayed one
    assert (backend.engine.phase, backend.overlay.isVisible()) == (Phase.STARTING, True)
    engine.started_ok.emit("dxcam")
    assert (backend.engine.phase, backend.overlay.isVisible()) == (Phase.RUNNING, True)


def test_a_hidden_overlay_stays_hidden_through_a_start(backend: Backend) -> None:
    backend.setOverlayVisible(False)
    backend.start()
    backend.engine._engine.started_ok.emit("dxcam")
    assert backend.engine.phase is Phase.RUNNING
    assert not backend.overlay.isVisible()
