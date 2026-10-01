"""Backend.setRoute while the engine is running, with only the engine thread stubbed.

Switching to a route on another map has to point the running engine at that map. The slot
called `EngineController.configure`, which the Backend split in #8 had renamed to
`reconfigure`, so the switch raised AttributeError: the engine kept matching the old map and
the new state was never sent. Found by the type checker, which reports a missing attribute on
sight; nothing else in the suite called this branch.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.bridge.engine_controller import Phase
from map_overlay.core.paths import DataDirs
from map_overlay.store import routes
from map_overlay.store.maps import MapSpec


def route_on(dirs: DataDirs, spec: MapSpec, name: str) -> str:
    """One route drawn on a bundled map. Returns the route id."""
    route_id = f"route-{name}"
    routes.save_route(dirs, route_id, routes.new_route_doc(name, spec.id, list(spec.size)))
    return route_id


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def test_switching_to_a_route_on_another_map_retargets_the_running_engine(
    backend: Backend,
    dirs: DataDirs,
    bundled: tuple[MapSpec, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altgard, verteron = bundled
    first_route = route_on(dirs, altgard, "first")
    second_route = route_on(dirs, verteron, "second")
    backend.setRoute(first_route)

    # Running as far as the controller can tell, without a thread capturing the screen.
    monkeypatch.setattr(backend.engine, "_phase", Phase.RUNNING)
    pushed: list[dict[str, Any]] = []
    monkeypatch.setattr(backend.engine._engine, "configure", lambda **kw: pushed.append(kw))
    states: list[str] = []
    backend.stateChanged.connect(states.append)

    backend.setRoute(second_route)

    assert pushed == [{"reference": str(verteron.reference), "reference_size": list(verteron.size)}]
    assert backend.route == second_route
    assert states, "the UI must be told the active route changed"


def test_switching_between_routes_on_the_same_map_leaves_the_engine_alone(
    backend: Backend,
    dirs: DataDirs,
    bundled: tuple[MapSpec, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    altgard, _ = bundled
    first_route = route_on(dirs, altgard, "first")
    second_route = route_on(dirs, altgard, "second")
    backend.setRoute(first_route)

    monkeypatch.setattr(backend.engine, "_phase", Phase.RUNNING)
    pushed: list[dict[str, Any]] = []
    monkeypatch.setattr(backend.engine._engine, "configure", lambda **kw: pushed.append(kw))

    backend.setRoute(second_route)

    assert pushed == []
    assert backend.route == second_route
