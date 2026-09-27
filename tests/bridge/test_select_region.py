"""Backend.selectRegion: a drawn area reaches the panel at once.

It used to be stored and never sent: the panel went on showing "no area" until something else
changed the state. On a stand-in carrying only what the slot reaches for, as in
test_start_picks_area.py, with the picker answering at once.
"""

from collections.abc import Callable
from types import SimpleNamespace

from map_overlay.bridge.backend import Backend

REGION: dict[str, int] = {"left": 40, "top": 60, "width": 800, "height": 600}


class StandIn:
    select_region = Backend.selectRegion
    _pick_region = Backend._pick_region
    _apply_region = Backend._apply_region

    def __init__(self, drawn: dict[str, int] | None) -> None:
        self.running = False
        self.state = SimpleNamespace(region=None)
        self.emitted: list[dict[str, int] | None] = []
        self._drawn = drawn
        self._store = SimpleNamespace(set_state=self._set_state)
        self._windows = SimpleNamespace(pick_region=self._picker)
        self.engine = SimpleNamespace(reconfigure=lambda **_: None)

    def _set_state(self, *, region: dict[str, int]) -> None:
        self.state.region = region

    def _picker(self, _prompt: str, on_picked: Callable[[dict[str, int]], None], _keep) -> None:
        if self._drawn:  # Esc hands nothing back
            on_picked(self._drawn)

    def _notify(self, *_args: object, **_params: object) -> None:
        pass

    def _emit_state(self) -> None:
        self.emitted.append(self.state.region)


def test_the_drawn_area_is_sent_to_the_panel() -> None:
    backend = StandIn(dict(REGION))

    backend.select_region()

    assert backend.emitted == [REGION]


def test_esc_sends_nothing() -> None:
    backend = StandIn(None)

    backend.select_region()

    assert backend.emitted == []
