"""The updater as the page reaches it: Backend's four slots, updateChanged and getState()["update"].

These build the real Backend, with only Velopack replaced, because what is pinned here is the
wiring: that Restart now saves and stops the app's own pieces before Velopack ends the process,
and that a downloaded update is handed over only after shutdown, with the settings on disk.
"""

import json
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fake_velopack import FakeAsset, Script, factory_for, found
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from map_overlay.bridge.backend import Backend
from map_overlay.core.paths import DataDirs
from map_overlay.updater.feed import DEFAULT_FEED, OVERRIDE_ENV
from map_overlay.updater.service import Phase

WAIT_MS = 5000

MakeBackend = Callable[..., Backend]


@pytest.fixture
def make_backend(qapp: QApplication, dirs: DataDirs, qtbot: QtBot) -> Iterator[MakeBackend]:
    built: list[Backend] = []

    def build(script: Script | None = None) -> Backend:
        backend = Backend(dirs, update_factory=factory_for(script) if script else None)
        built.append(backend)
        qtbot.waitUntil(lambda: not backend._updates.busy, timeout=WAIT_MS)
        return backend

    yield build
    for backend in built:
        backend.shutdown()


def record(journal: list[str], name: str, real: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        journal.append(name)
        return real(*args, **kwargs)

    return wrapper


def test_a_source_checkout_reports_updates_as_disabled(make_backend: MakeBackend) -> None:
    backend = make_backend()  # the real Velopack: this test process is not an install

    assert json.loads(backend.getState())["update"] == {"phase": "disabled"}


def test_the_slots_drive_the_updater_and_updatechanged_carries_every_step(
    make_backend: MakeBackend, qtbot: QtBot
) -> None:
    backend = make_backend(Script(offer=found("1.2.0")))
    updates: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    backend.updateChanged.connect(lambda raw: updates.append(json.loads(raw)))
    backend.stateChanged.connect(lambda raw: states.append(json.loads(raw)))

    backend.checkForUpdates()
    qtbot.waitUntil(lambda: backend._updates.phase is Phase.READY, timeout=WAIT_MS)

    assert [u.get("progress") for u in updates if u["phase"] == "downloading"] == [0, 70, 100]
    # The whole state follows a change of phase, not every progress tick.
    assert [s["update"]["phase"] for s in states] == ["checking", "downloading", "ready"]
    assert json.loads(backend.getState())["update"]["version"] == "1.2.0"


def test_skip_update_is_stored_and_shown(make_backend: MakeBackend) -> None:
    backend = make_backend(Script(pending=FakeAsset("1.2.0")))
    states: list[dict[str, Any]] = []
    backend.stateChanged.connect(lambda raw: states.append(json.loads(raw)))

    backend.skipUpdate("1.2.0")

    assert states[-1]["settings"]["updates_skipped_version"] == "1.2.0"
    assert states[-1]["update"]["skipped"] is True


def test_turning_automatic_checks_off_and_on_reaches_the_timer(make_backend: MakeBackend) -> None:
    backend = make_backend(Script())
    assert backend._updates.auto_check_pending

    backend.updateSettings(json.dumps({"updates_auto_check": False}))
    assert not backend._updates.auto_check_pending
    backend.updateSettings(json.dumps({"updates_auto_check": True}))
    assert backend._updates.auto_check_pending


def test_restart_now_saves_and_stops_everything_before_velopack_ends_the_process(
    make_backend: MakeBackend, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal: list[str] = []
    backend = make_backend(Script(pending=FakeAsset("1.2.0"), journal=journal))
    for target, name, label in (
        (backend._store, "flush", "flush"),
        (backend.engine, "shutdown", "engine_stop"),
        (backend._windows, "hide_all", "windows_hidden"),
    ):
        monkeypatch.setattr(target, name, record(journal, label, getattr(target, name)))
    journal.clear()

    backend.installUpdate(True)

    assert journal == ["flush", "engine_stop", "windows_hidden", "flush", "apply_restart"]


def test_a_failed_restart_now_leaves_the_app_usable(
    make_backend: MakeBackend, qtbot: QtBot
) -> None:
    """The windows were only hidden: the plaque keeps its page and its channel for later."""
    script = Script(pending=FakeAsset("1.2.0"), apply_error=RuntimeError("Update.exe missing"))
    backend = make_backend(script)
    channel = backend.steps.view.page().webChannel()

    backend.installUpdate(True)
    qtbot.waitUntil(lambda: backend._updates.phase is Phase.FAILED, timeout=WAIT_MS)

    assert backend.steps.view.page().webChannel() is channel
    assert not backend.overlay.isVisible()
    assert json.loads(backend.getState())["update"]["stage"] == "install"


def test_a_failed_restart_now_puts_the_steps_plaque_back(
    make_backend: MakeBackend, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """hide_all() took it down; the state still says it is on, so it has to come back."""
    journal: list[str] = []
    script = Script(pending=FakeAsset("1.2.0"), apply_error=RuntimeError("Update.exe missing"))
    backend = make_backend(script)
    monkeypatch.setattr(backend, "_sync_steps", record(journal, "sync_steps", backend._sync_steps))

    backend.installUpdate(True)
    qtbot.waitUntil(lambda: backend._updates.phase is Phase.FAILED, timeout=WAIT_MS)

    assert journal == ["sync_steps"]


def test_a_skip_set_through_update_settings_reaches_the_updater(
    make_backend: MakeBackend,
) -> None:
    script = Script(pending=FakeAsset("1.2.0"))
    backend = make_backend(script)
    updates: list[dict[str, Any]] = []
    backend.updateChanged.connect(lambda raw: updates.append(json.loads(raw)))

    backend.updateSettings(json.dumps({"updates_skipped_version": "1.2.0"}))

    assert updates[-1]["skipped"] is True
    assert not backend._updates.apply_on_exit
    backend.hand_over_update()
    assert "apply_after_exit" not in script.names()


def test_shutdown_hands_a_ready_update_over_only_after_the_settings_are_written(
    qapp: QApplication, qtbot: QtBot, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal: list[str] = []
    # Built by hand: this test runs shutdown itself, and a second one would warn.
    script = Script(pending=FakeAsset("1.2.0"), journal=journal)
    backend = Backend(dirs, update_factory=factory_for(script))
    qtbot.waitUntil(lambda: backend._updates.phase is Phase.READY, timeout=WAIT_MS)
    backend.updateSettings(json.dumps({"opacity": 0.5}))  # debounced: not on disk yet
    for target, name, label in (
        (backend._store, "flush", "flush"),
        (backend.engine, "shutdown", "engine_stop"),
    ):
        monkeypatch.setattr(target, name, record(journal, label, getattr(target, name)))
    journal.clear()

    backend.shutdown()
    # Not from the window's close event: main() hands over after the event loop is over.
    assert journal == ["flush", "engine_stop"]
    assert json.loads(dirs.settings.read_text(encoding="utf-8"))["opacity"] == 0.5

    backend.hand_over_update()
    assert journal == ["flush", "engine_stop", "apply_after_exit"]


def test_no_file_the_app_reads_can_move_the_feed(
    qapp: QApplication, dirs: DataDirs, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(OVERRIDE_ENV, raising=False)
    dirs.settings.write_text(
        json.dumps({"version": 1, "update_url": "https://evil.example/"}), encoding="utf-8"
    )
    backend = Backend(dirs)
    try:
        backend.updateSettings(json.dumps({"update_url": "https://evil.example/"}))
        assert backend._updates.feed == DEFAULT_FEED
        assert "update_url" not in json.loads(backend.getState())["settings"]
    finally:
        backend.shutdown()
