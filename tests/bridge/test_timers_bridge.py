"""The timers through Backend: getState carries them, the slots store the user's choices as
settings, and every change reaches the pages on timersChanged."""

import json
import threading
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.timers import data as timers_data


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


def timers_of(backend: Backend) -> dict[str, Any]:
    state = json.loads(backend.getState())
    assert state["api"] == 35
    return state["timers"]


def sent(backend: Backend) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    backend.timersChanged.connect(lambda payload: out.append(json.loads(payload)))
    return out


def test_get_state_carries_the_timers(backend: Backend) -> None:
    timers = timers_of(backend)
    ids = {e["id"] for e in timers["events"]}
    assert {"rift", "shugo-festival", "artifact-siege", "daily-reset"} <= ids
    assert timers["region"] and timers["regions"]


def test_a_choice_for_one_event_is_a_setting_and_is_sent(backend: Backend) -> None:
    seen = sent(backend)
    backend.setTimerEvent("rift", json.dumps({"lead": 10}))
    backend.setTimerEvent("rift", json.dumps({"signal": "voice"}))
    assert backend.settings.timers_events == {"rift": {"lead": 10, "signal": "voice"}}
    rift = next(e for e in seen[-1]["events"] if e["id"] == "rift")
    assert (rift["lead"], rift["signal"]) == (10, "voice")


def test_a_choice_the_timers_do_not_offer_is_dropped(backend: Backend) -> None:
    backend.setTimerEvent("rift", json.dumps({"lead": 7, "colour": "red"}))
    assert backend.settings.timers_events == {}
    backend.setTimerEvent("rift", "not json")
    backend.setTimerEvent("rift", json.dumps(["lead", 5]))
    assert backend.settings.timers_events == {}


def test_the_world_bosses_shown_are_a_setting(backend: Backend) -> None:
    backend.setTimersWorldShown(json.dumps(["melted-danar", "melted-danar", "sharp-shylak"]))
    assert backend.settings.timers_world_shown == ["melted-danar", "sharp-shylak"]
    backend.setTimersWorldShown("{}")
    assert backend.settings.timers_world_shown == ["melted-danar", "sharp-shylak"]


def test_a_region_chosen_in_settings_is_the_one_shown(backend: Backend) -> None:
    seen = sent(backend)
    backend.updateSettings(json.dumps({"timers_region": "kr"}))
    assert seen[-1]["region"] == "kr" and not seen[-1]["regionGuessed"]


def test_a_reset_of_the_settings_keeps_the_timers_choices(backend: Backend) -> None:
    backend.setTimerEvent("rift", json.dumps({"lead": 15}))
    backend.updateSettings(json.dumps({"timers_region": "kr", "opacity": 0.5}))
    backend.resetSettings()
    assert backend.settings.opacity == 0.85
    assert backend.settings.timers_region == "kr"
    assert backend.settings.timers_events == {"rift": {"lead": 15}}


def test_a_fetch_the_user_asked_for_that_fails_says_so(
    backend: Backend, monkeypatch: pytest.MonkeyPatch
) -> None:
    def down(url: str, _etag: str | None) -> timers_data.Fetched:
        raise timers_data.FetchError(f"{url}: offline")

    monkeypatch.setattr(timers_data, "http_transport", down)
    notices: list[dict[str, Any]] = []
    backend.notify.connect(lambda payload: notices.append(json.loads(payload)))
    backend.refreshTimersData()
    for thread in threading.enumerate():
        if thread.name == "timers-fetch":
            thread.join(5)
    for _ in range(20):
        QCoreApplication.processEvents()
    assert [n["code"] for n in notices] == ["timers.fetch_failed"]
    assert timers_of(backend)["events"], "the bundled schedule stays in use"
