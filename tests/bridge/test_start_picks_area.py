"""Start with no map area yet: it asks for one, and starts once the box is drawn.

A new user used to press Start and be told to go and find the button that selects the area.
Now Start opens the picker itself. What has to hold: the engine starts only on an area that was
actually drawn, Esc starts nothing, a Start with an area goes straight ahead, and a route that
cannot run is refused before the user is asked to draw anything.

Backend.start runs here on a stand-in carrying only what it reaches for, as the plaque's data
is read in test_marker_icons.py: a real Backend brings three web views, and the session's Qt
WebEngine has room for few of them.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QRect

from map_overlay.bridge import backend as backend_module
from map_overlay.bridge.backend import Backend
from map_overlay.core.settings import Settings
from map_overlay.qt.region_selector import RegionSelector

REGION: dict[str, int] = {"left": 40, "top": 60, "width": 800, "height": 600}


class StandIn:
    """The Backend fields start() reads, with the picker and the engine recorded, not run."""

    start = Backend.start
    _start_in = Backend._start_in
    _apply_region = Backend._apply_region

    def __init__(self, region: dict[str, int] | None, error: str | None = None) -> None:
        self.running = False
        self.route = "quests"
        self.settings = Settings()
        self.state = SimpleNamespace(region=region)
        self.prompts: list[str] = []
        self.pending: list[Callable[[dict[str, int]], None]] = []
        self.engine_starts: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self._error = error
        self._store = SimpleNamespace(set_state=self._set_state)
        self._routes = SimpleNamespace(runnable_route=self._runnable_route)
        self._notifier = SimpleNamespace(from_error=self.errors.append)
        self.engine = SimpleNamespace(start=self._engine_start, reconfigure=lambda **_: None)
        self.overlay = SimpleNamespace(set_region=lambda _: None)

    def _set_state(self, *, region: dict[str, int]) -> None:
        self.state.region = region

    def _runnable_route(self, _route: str) -> tuple[dict[str, Any], str, str | None]:
        return {"markers": []}, "reference.webp", self._error

    def _engine_start(self, **config: Any) -> None:
        self.engine_starts.append(config)
        self.running = True

    def _revalidate_screens(self) -> bool:
        return False

    def _pick_region(self, prompt: str, apply: Callable[[dict[str, int]], None]) -> None:
        self.prompts.append(prompt)
        self.pending.append(apply)

    def _apply_route(self, _doc: dict[str, Any]) -> None:
        pass

    def _emit_state(self) -> None:
        pass

    def draw(self, region: dict[str, int]) -> None:
        """The user drags the box out: the picker hands it to whoever asked."""
        self.pending.pop()(region)


@pytest.fixture(autouse=True)
def screen(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_module, "primary_screen_geometry", lambda: QRect(0, 0, 1920, 1080))


def test_start_with_no_area_asks_for_one_and_waits() -> None:
    backend = StandIn(region=None)
    backend.start()
    assert backend.prompts == [RegionSelector.START_PROMPT]
    assert backend.engine_starts == []


def test_the_drawn_area_is_kept_and_the_overlay_starts_on_it() -> None:
    backend = StandIn(region=None)
    backend.start()
    backend.draw(REGION)
    assert backend.state.region == REGION
    assert [s["region"] for s in backend.engine_starts] == [REGION]


def test_esc_in_the_picker_starts_nothing() -> None:
    backend = StandIn(region=None)
    backend.start()
    backend.pending.clear()  # cancelled: the picker never calls back
    assert backend.engine_starts == []
    assert backend.state.region is None


def test_start_with_an_area_goes_straight_ahead() -> None:
    backend = StandIn(region=REGION)
    backend.start()
    assert backend.prompts == []
    assert [s["region"] for s in backend.engine_starts] == [REGION]


def test_a_route_that_cannot_run_is_refused_before_anything_is_drawn() -> None:
    backend = StandIn(region=None, error="route.required")
    backend.start()
    assert backend.errors == ["route.required"]
    assert backend.prompts == []
