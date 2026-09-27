"""Backend.resetRegion: the map area is forgotten, and a running engine stops before it goes.

On a stand-in carrying only what the slot reaches for, as in test_start_picks_area.py: a real
Backend brings three web views, and the session's Qt WebEngine has room for few of them.
"""

from types import SimpleNamespace

from map_overlay.bridge.backend import Backend

REGION: dict[str, int] = {"left": 40, "top": 60, "width": 800, "height": 600}


class StandIn:
    reset_region = Backend.resetRegion

    def __init__(self, region: dict[str, int] | None, running: bool) -> None:
        self.running = running
        self.state = SimpleNamespace(region=region)
        self.events: list[str] = []
        self._store = SimpleNamespace(set_state=self._set_state)

    def _set_state(self, *, region: dict[str, int] | None) -> None:
        self.events.append("cleared")
        self.state.region = region

    def stop(self) -> None:
        self.events.append("stopped" if self.running else "stop")
        self.running = False

    def _emit_state(self) -> None:
        self.events.append("emitted")


def test_forgets_the_area_and_tells_the_page() -> None:
    backend = StandIn(dict(REGION), running=False)

    backend.reset_region()

    assert backend.state.region is None
    assert backend.events[-2:] == ["cleared", "emitted"]


def test_a_running_engine_stops_before_the_area_goes() -> None:
    backend = StandIn(dict(REGION), running=True)

    backend.reset_region()

    assert backend.events == ["stopped", "cleared", "emitted"]
    assert not backend.running


def test_without_an_area_nothing_happens() -> None:
    backend = StandIn(None, running=True)

    backend.reset_region()

    assert backend.events == []
    assert backend.running
