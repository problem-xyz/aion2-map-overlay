"""The Feathers switch leaves the route's points on Empyrean Traces out of what the player sees.

Off, the overlay, the plaque and the panel's progress get the route without them, numbered and
counted as if it had none. The count kept on disk stays the whole route's, so turning the
feathers back on finds the progress where it was, and a feather passed over while they were off
counts as passed.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.progress import ProgressTracker
from map_overlay.core.fileio import atomic_write_json
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes

ROUTE = "feathers"
SIZE = 1000
# Five points; the second and the fourth stand on feathers.
POINTS = [(10.0, 10.0), (20.0, 10.0), (30.0, 10.0), (40.0, 10.0), (50.0, 10.0)]
FEATHERS = {1, 3}
KEPT = [i for i in range(len(POINTS)) if i not in FEATHERS]


def tracker(done: int) -> ProgressTracker:
    state = SimpleNamespace(route="r", progress={"r": done})

    def set_state(**fields: object) -> None:
        state.progress = fields["progress"]

    made = ProgressTracker(SimpleNamespace(state=state, set_state=set_state))
    made.set_view(KEPT, len(POINTS))
    return made


SHOWN = {"markers": [{} for _ in KEPT]}


@pytest.mark.parametrize(("whole", "shown"), [(0, 0), (1, 1), (2, 1), (3, 2), (4, 2), (5, 3)])
def test_the_count_shown_is_the_points_shown_before_the_next(whole: int, shown: int) -> None:
    assert tracker(whole).done_count(SHOWN) == shown


@pytest.mark.parametrize(("shown", "whole"), [(0, 0), (1, 2), (2, 4), (3, 5)])
def test_a_point_passed_passes_the_feathers_after_it(shown: int, whole: int) -> None:
    made = tracker(0 if shown else 1)
    made.set_done(shown, SHOWN)

    assert made._progress["r"] == whole


# ------------------------------------------------------------------ the backend's part

A_SET = {
    "mapName": "Altgard",
    "categories": [{"id": "empyrean-trace-altgard", "name": "Empyrean Trace", "color": "#38bdf8"}],
    "nodes": [
        {"categoryId": "empyrean-trace-altgard", "x": POINTS[i][0] / SIZE * 100, "y": 1.0}
        for i in FEATHERS
    ],
}


@pytest.fixture
def shipped_set(test_maps_root: Callable[[], Path]) -> Iterator[Path]:
    path = test_maps_root().parent / "object-sets" / "altgard.json"
    atomic_write_json(path, A_SET)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs, shipped_set: Path) -> Iterator[Backend]:
    doc = routes.new_route_doc("Feathers", "altgard", [SIZE, SIZE])
    doc["markers"] = [{"x": x, "y": y} for x, y in POINTS]
    routes.save_route(dirs, ROUTE, doc)
    made = Backend(dirs)
    try:
        made.setRoute(ROUTE)
        yield made
    finally:
        made.shutdown()


def feathers(backend: Backend, on: bool) -> None:
    backend.updateSettings(json.dumps({"route_traces": on}))


def drawn(backend: Backend) -> list[float]:
    pts = backend.overlay._pts
    return [] if pts is None else [float(x) for x in pts[:, 0, 0]]


def test_the_feathers_are_in_the_route_by_default(backend: Backend) -> None:
    assert backend.settings.route_traces
    assert drawn(backend) == [x for x, _y in POINTS]
    assert backend._state()["progress"]["total"] == len(POINTS)


def test_off_they_go_from_the_overlay_the_plaque_and_the_progress(backend: Backend) -> None:
    feathers(backend, False)

    assert drawn(backend) == [POINTS[i][0] for i in KEPT]
    assert len(backend.steps._steps) == len(KEPT)
    progress = backend._state()["progress"]
    assert progress["total"] == len(KEPT)
    assert [m["n"] for m in progress["markers"]] == [1, 2, 3]


def test_progress_made_without_them_is_kept_when_they_come_back(backend: Backend) -> None:
    feathers(backend, False)
    backend.setProgress(2)  # the first two points shown: points 1 and 3, the feather between

    feathers(backend, True)
    assert backend._state()["progress"]["done"] == 4  # the feather after point 3 as well
