"""Backend.resetSettings: back to the defaults, on disk, and in everything holding a copy.

The store's half -- which fields survive (KEPT_ON_RESET), and that the write is the usual
debounced one -- is pinned in test_settings_store.py. What is pinned here is the facade's half:
a reset reaches the overlay, the plaque and the engine exactly as the same values set one by
one would.
"""

import json
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge import backend as backend_module
from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Region, Settings, plaque_scale, settings_payload

CHANGED = {
    "opacity": 0.4,
    "fps": 90,
    "detector": "orb",
    "min_inliers": 40,
    "steps_size": "l",
    "steps_pinned": False,
    "capture_visible": True,
    "route_view": "dim",
    "route_ahead": 5,
    "route_past": 7,
}


@pytest.fixture
def backend(
    qapp: QApplication, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Backend]:
    # A Windows that can hide windows from capture, whatever machine the suite runs on.
    monkeypatch.setattr(backend_module, "windows_version", lambda: (10, 0, 26100))
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def listen(backend: Backend) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    notices: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    backend.notify.connect(lambda raw: notices.append(json.loads(raw)))
    backend.stateChanged.connect(lambda raw: states.append(json.loads(raw)))
    return notices, states


def test_reset_puts_every_setting_back_and_writes_the_file(
    backend: Backend, dirs: DataDirs
) -> None:
    backend.updateSettings(json.dumps(CHANGED))
    assert backend.settings != Settings()

    backend.resetSettings()
    backend._store.flush()

    assert backend.settings == Settings()
    assert json.loads(dirs.settings.read_text(encoding="utf-8")) == settings_payload(Settings())


def test_reset_is_applied_to_the_windows_and_the_engine(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend.updateSettings(json.dumps(CHANGED))
    reconfigured: list[dict[str, Any]] = []
    monkeypatch.setattr(backend.engine, "reconfigure", lambda **kw: reconfigured.append(kw))

    backend.resetSettings()

    assert backend.overlay._opacity == Settings.opacity
    assert backend.overlay._view == (Settings.route_view, Settings.route_ahead, Settings.route_past)
    assert backend.overlay._recordable is False  # capture_visible is off again
    plaque = json.loads(backend.steps.data_json())
    assert (plaque["scale"], plaque["size"], plaque["pinned"], plaque["opacity"]) == (
        plaque_scale(Settings.steps_scale),
        "l",  # the old step nearest the default's 1.35
        Settings.steps_pinned,
        Settings.opacity,
    )
    assert plaque["past"] == Settings.route_past
    assert reconfigured == [{"settings": asdict(Settings())}]


def test_reset_says_so_and_sends_the_state_even_when_nothing_changed(backend: Backend) -> None:
    """The panel may hold an edit it never sent and dropped on confirming: it must be told."""
    notices, states = listen(backend)

    backend.resetSettings()

    assert [n["code"] for n in notices] == ["settings.reset"]
    assert notices[0]["level"] == "info"
    assert len(states) == 1
    assert states[0]["settings"] == asdict(Settings())


def test_reset_keeps_the_updater_fields(backend: Backend) -> None:
    backend.updateSettings(
        json.dumps({"updates_auto_check": False, "updates_skipped_version": "1.2.0", "fps": 90})
    )

    backend.resetSettings()

    assert backend.settings == Settings(updates_auto_check=False, updates_skipped_version="1.2.0")


def test_reset_leaves_the_map_area_alone(backend: Backend) -> None:
    """The map area is state, not a setting: resetting preferences must not make the user
    pick it again."""
    region = Region(left=100, top=100, width=400, height=300)
    backend._store.set_state(region=region)

    backend.resetSettings()

    assert backend.state.region == region
