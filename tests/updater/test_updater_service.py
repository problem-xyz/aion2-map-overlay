"""UpdaterService's state machine, driven against a scripted fake of Velopack.

Every Velopack call runs on a worker thread and its outcome comes back as a queued signal, so
nothing below happens until the event loop turns: the tests wait with qtbot.waitUntil, and each
records the ordered list of phases the service announced rather than only the one it ends on. A
machine that skipped `checking` or went `available` before `downloading` would end in the right
place and still be wrong.

Delays are real QTimers with the intervals shrunk, never a call to the timer's private slot, so
the scheduling tests measure the timer the app uses.
"""

import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from typing import Any

import pytest
from fake_velopack import TIMEOUT, FakeAsset, Script, factory_for, found
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from map_overlay.core.settings import Settings
from map_overlay.updater import manager, service
from map_overlay.updater.feed import Feed, FeedKind
from map_overlay.updater.service import Phase, UpdaterService

WAIT_MS = 5000
FEED = Feed(FeedKind.FOLDER, "C:/Releases", overridden=True)
# Far enough off that no test sees an automatic check it did not ask for.
NEVER_MS = 600_000


@dataclass
class Harness:
    """The service plus everything it reported: phases, payloads, notices and settings."""

    svc: UpdaterService
    script: Script
    settings: list[Settings]
    payloads: list[dict[str, Any]] = field(default_factory=list)
    notices: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    emit_threads: list[int] = field(default_factory=list)
    prepared: list[str] = field(default_factory=list)
    resumed: int = 0

    @property
    def phases(self) -> list[str]:
        """Each phase once, in order: progress ticks repeat `downloading` and are folded."""
        out: list[str] = []
        for payload in self.payloads:
            if not out or out[-1] != payload["phase"]:
                out.append(payload["phase"])
        return out

    def codes(self) -> list[str]:
        return [code for _, code, _ in self.notices]

    @property
    def current(self) -> Settings:
        return self.settings[-1]


Make = Callable[..., Harness]


@pytest.fixture
def make(qapp: QApplication, qtbot: QtBot) -> Iterator[Make]:
    built: list[Harness] = []

    def build(
        script: Script | None = None,
        *,
        start: bool = True,
        first_check_ms: int = NEVER_MS,
        interval_ms: int = NEVER_MS,
        prepare_exit: Callable[[], None] | None = None,
        **settings: Any,
    ) -> Harness:
        script = script or Script()
        box = [Settings(**settings)]
        harness_ref: list[Harness] = []

        def update_settings(patch: dict[str, Any]) -> Settings:
            box.append(replace(box[-1], **patch))
            return box[-1]

        def notify(level: str, code: str, /, **params: Any) -> None:
            harness_ref[0].notices.append((level, code, params))

        def prepared() -> None:
            harness_ref[0].prepared.append("prepare_exit")
            if script.journal is not None:
                script.journal.append("prepare_exit")

        def resumed() -> None:
            harness_ref[0].resumed += 1

        svc = UpdaterService(
            settings=lambda: box[-1],
            update_settings=update_settings,
            notify=notify,
            prepare_exit=prepare_exit or prepared,
            resume_after_failed_exit=resumed,
            factory=factory_for(script),
            feed=FEED,
            first_check_ms=first_check_ms,
            interval_ms=interval_ms,
        )
        harness = Harness(svc, script, box)
        harness_ref.append(harness)

        def on_state(payload: dict[str, Any]) -> None:
            harness.payloads.append(payload)
            harness.emit_threads.append(threading.get_ident())

        # Direct, so that on_state runs on whichever thread the service emitted from: a plain
        # function connected the default way would be queued back to the GUI thread and hide it.
        svc.stateChanged.connect(on_state, Qt.ConnectionType.DirectConnection)
        built.append(harness)
        if start:
            svc.start()
            qtbot.waitUntil(lambda: not svc.busy, timeout=WAIT_MS)
        return harness

    yield build
    for harness in built:
        if harness.script.gate is not None:
            harness.script.gate.set()
        harness.svc.close()


def settle(qtbot: QtBot, harness: Harness) -> None:
    qtbot.waitUntil(lambda: not harness.svc.busy, timeout=WAIT_MS)


# ---------------------------------------------------------------------------- start-up


def test_a_copy_velopack_did_not_install_stays_disabled(make: Make, qtbot: QtBot) -> None:
    h = make(Script(installed=False))

    assert h.svc.phase is Phase.DISABLED
    assert h.svc.snapshot() == {"phase": "disabled"}
    assert not h.svc.auto_check_pending
    h.svc.check()
    h.svc.download()
    h.svc.install(True)
    assert not h.svc.busy
    assert h.script.names() == []  # the constructor raised; no manager was ever built again
    assert h.prepared == []
    assert h.notices == []


def test_the_real_velopack_outside_an_install_is_disabled(
    qapp: QApplication, qtbot: QtBot, caplog: pytest.LogCaptureFixture
) -> None:
    """This test process is a source checkout, which is what `disabled` is for."""
    caplog.set_level(logging.INFO, logger="map_overlay.updater")
    svc = UpdaterService(
        settings=Settings,
        update_settings=lambda patch: None,
        notify=lambda level, code, /, **params: None,
        prepare_exit=lambda: None,
        feed=FEED,
        first_check_ms=NEVER_MS,
    )
    try:
        svc.start()
        qtbot.waitUntil(lambda: not svc.busy, timeout=WAIT_MS)
        assert svc.phase is Phase.DISABLED
        assert not svc.auto_check_pending
        assert any("not properly installed" in r.getMessage() for r in caplog.records)
    finally:
        svc.close()


def test_an_install_goes_idle_and_arms_the_automatic_check(make: Make) -> None:
    h = make()

    assert h.phases == ["idle"]
    assert h.svc.auto_check_pending
    assert h.script.names() == ["pending"]


def test_a_package_left_by_an_earlier_run_is_ready_and_applied_on_exit(make: Make) -> None:
    h = make(Script(pending=FakeAsset("1.2.0", "notes")))

    assert h.phases == ["ready"]
    assert h.svc.snapshot() == {
        "phase": "ready",
        "version": "1.2.0",
        "notes": "notes",
        "skipped": False,
    }
    assert h.codes() == ["update.ready"]
    h.svc.hand_over()
    assert h.script.calls[-1].name == "apply_after_exit"
    assert h.script.calls[-1].args[1:] == (True, False)  # silent, and no restart


# ---------------------------------------------------------------------------- checking


def test_a_check_that_finds_nothing_ends_in_none_without_a_notice(make: Make, qtbot: QtBot) -> None:
    h = make()
    h.svc.check()
    settle(qtbot, h)

    assert h.phases == ["idle", "checking", "none"]
    assert h.notices == []


def test_a_version_found_without_auto_download_is_offered_without_a_toast(
    make: Make, qtbot: QtBot
) -> None:
    h = make(Script(offer=found("1.2.0", "- faster")), updates_auto_download=False)
    h.svc.check()
    settle(qtbot, h)

    assert h.phases == ["idle", "checking", "available"]
    assert h.svc.snapshot() == {
        "phase": "available",
        "version": "1.2.0",
        "notes": "- faster",
        "skipped": False,
    }
    # The banner offers it; a toast in the same window would say the same thing twice.
    assert h.notices == []
    assert "download" not in h.script.names()


def test_auto_download_goes_straight_on_and_announces_only_ready(make: Make, qtbot: QtBot) -> None:
    h = make(Script(offer=found("1.2.0")))
    h.svc.check()
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)

    assert h.phases == ["idle", "checking", "downloading", "ready"]
    progress = [p["progress"] for p in h.payloads if p["phase"] == "downloading"]
    assert progress == [0, 70, 100]
    assert h.notices == [("info", "update.ready", {"version": "1.2.0"})]
    assert h.script.timeouts[-1] == manager.DOWNLOAD_TIMEOUT_MS
    assert h.script.timeouts[-2] == manager.CHECK_TIMEOUT_MS
    # Not handed to Update.exe while the app runs: it would kill the app 60 s later.
    assert h.svc.apply_on_exit
    assert "apply_after_exit" not in h.script.names()
    qtbot.wait(100)
    assert "apply_after_exit" not in h.script.names()
    h.svc.hand_over()
    assert h.script.names()[-1] == "apply_after_exit"


def test_progress_crosses_threads_and_reaches_the_gui_thread_queued(
    make: Make, qtbot: QtBot
) -> None:
    """Velopack calls the progress callback on the thread that called download_updates."""
    h = make(Script(offer=found("1.2.0"), progress=[0, 50, 40, 150]))
    h.svc.check()
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)

    gui = threading.get_ident()
    download = next(c for c in h.script.calls if c.name == "download")
    assert download.thread != gui
    assert set(h.emit_threads) == {gui}
    # Clamped to 0-100 and never backwards.
    assert [p["progress"] for p in h.payloads if p["phase"] == "downloading"] == [0, 50, 100]


def test_a_skipped_version_is_neither_downloaded_nor_announced(make: Make, qtbot: QtBot) -> None:
    h = make(Script(offer=found("1.2.0")), updates_skipped_version="1.2.0")
    h.svc.check()
    settle(qtbot, h)

    assert h.phases == ["idle", "checking", "available"]
    assert h.svc.snapshot().get("skipped") is True
    assert "download" not in h.script.names()
    assert h.notices == []


def test_a_newer_version_than_the_skipped_one_is_downloaded(make: Make, qtbot: QtBot) -> None:
    h = make(Script(offer=found("1.3.0")), updates_skipped_version="1.2.0")
    h.svc.check()
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)
    assert h.codes() == ["update.ready"]


# ---------------------------------------------------------------------------- guards


def test_overlapping_requests_are_ignored_while_a_worker_runs(make: Make, qtbot: QtBot) -> None:
    gate = threading.Event()
    h = make(Script(offer=found("1.2.0"), gate=gate), updates_auto_download=False)

    h.svc.check()
    h.svc.check()
    h.svc.download()
    h.svc.install(True)
    h.svc.install(False)
    assert h.script.names() == ["pending", "check"]
    assert h.prepared == []

    gate.set()
    settle(qtbot, h)
    assert h.svc.phase is Phase.AVAILABLE

    gate.clear()
    h.svc.download()
    h.svc.download()
    h.svc.check()
    h.svc.install(True)
    assert h.script.names().count("download") == 1
    assert h.svc.phase is Phase.DOWNLOADING
    gate.set()
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)
    assert h.prepared == []

    h.svc.download()  # already downloaded
    h.svc.check()  # an armed release is not replaced mid-session
    assert h.script.names().count("download") == 1
    assert h.script.names().count("check") == 1


def test_install_before_anything_is_downloaded_does_nothing(make: Make) -> None:
    h = make()
    h.svc.install(True)
    h.svc.install(False)

    assert h.prepared == []
    assert "apply_restart" not in h.script.names()
    assert h.notices == []


# ---------------------------------------------------------------------------- failures


def test_a_timeout_becomes_failed_and_a_notice_never_an_exception(make: Make, qtbot: QtBot) -> None:
    error = RuntimeError(f"{TIMEOUT}\n\nCaused by:\n    timeout: global")
    h = make(Script(check_error=error))
    h.svc.check()
    settle(qtbot, h)

    assert h.phases == ["idle", "checking", "failed"]
    assert h.svc.snapshot() == {
        "phase": "failed",
        "code": "update.failed",
        "reason": TIMEOUT,
        "stage": "check",
    }
    assert h.notices == [("error", "update.failed", {"reason": TIMEOUT})]


def test_an_unexpected_exception_in_a_worker_is_a_failure_too(make: Make, qtbot: QtBot) -> None:
    h = make(Script(check_error=ValueError("bad feed")))
    h.svc.check()
    settle(qtbot, h)

    assert h.svc.snapshot().get("reason") == "bad feed"
    assert h.codes() == ["update.failed"]


class FakePanic(BaseException):
    """pyo3's PanicException derives from BaseException, not Exception, like this one."""


def test_a_rust_panic_in_a_worker_fails_and_frees_the_worker(make: Make, qtbot: QtBot) -> None:
    panic = FakePanic("called `Option::unwrap()` on a `None` value")
    h = make(Script(check_error=panic))
    h.svc.check()
    settle(qtbot, h)

    assert h.phases == ["idle", "checking", "failed"]
    assert h.svc.snapshot().get("reason") == "called `Option::unwrap()` on a `None` value"
    assert h.codes() == ["update.failed"]

    h.script.check_error = None
    h.svc.check()
    settle(qtbot, h)
    assert h.script.names().count("check") == 2
    assert h.svc.phase is Phase.NONE


def test_a_failed_download_keeps_its_version_and_can_be_retried(make: Make, qtbot: QtBot) -> None:
    h = make(Script(offer=found("1.2.0"), download_error=RuntimeError("IO error: disk full")))
    h.svc.check()
    settle(qtbot, h)

    assert h.svc.snapshot() == {
        "phase": "failed",
        "version": "1.2.0",
        "notes": "",
        "skipped": False,
        "code": "update.failed",
        "reason": "IO error: disk full",
        "stage": "download",
    }
    assert not h.svc.apply_on_exit

    h.script.download_error = None
    h.svc.download()
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)
    assert h.phases[-3:] == ["failed", "downloading", "ready"]


def test_repeated_automatic_failures_are_announced_once(make: Make, qtbot: QtBot) -> None:
    script = Script(check_error=RuntimeError(TIMEOUT))
    h = make(script, first_check_ms=10, interval_ms=30)

    qtbot.waitUntil(lambda: script.names().count("check") >= 3, timeout=WAIT_MS)
    settle(qtbot, h)
    assert h.notices == [("warning", "update.failed", {"reason": TIMEOUT})]

    script.check_error = None  # back online: the next success resets the streak
    qtbot.waitUntil(lambda: h.svc.phase is Phase.NONE, timeout=WAIT_MS)
    script.check_error = RuntimeError(TIMEOUT)
    qtbot.waitUntil(lambda: h.codes().count("update.failed") == 2, timeout=WAIT_MS)


# ---------------------------------------------------------------------------- scheduling


def test_the_first_automatic_check_waits_for_its_delay(make: Make, qtbot: QtBot) -> None:
    script = Script()
    h = make(script, first_check_ms=150)

    assert h.svc.auto_check_pending
    assert script.names() == ["pending"]
    qtbot.waitUntil(lambda: "check" in script.names(), timeout=WAIT_MS)
    settle(qtbot, h)
    assert h.svc.auto_check_pending  # re-armed for the next interval


def test_automatic_checks_repeat_every_interval(make: Make, qtbot: QtBot) -> None:
    script = Script()
    make(script, first_check_ms=10, interval_ms=40)
    qtbot.waitUntil(lambda: script.names().count("check") >= 3, timeout=WAIT_MS)


def test_no_automatic_check_while_the_setting_is_off(make: Make, qtbot: QtBot) -> None:
    script = Script()
    h = make(script, first_check_ms=10, updates_auto_check=False)
    assert not h.svc.auto_check_pending
    qtbot.wait(100)
    assert "check" not in script.names()

    h.settings.append(replace(h.current, updates_auto_check=True))
    h.svc.schedule_auto()
    assert h.svc.auto_check_pending
    qtbot.waitUntil(lambda: "check" in script.names(), timeout=WAIT_MS)
    settle(qtbot, h)

    h.settings.append(replace(h.current, updates_auto_check=False))
    h.svc.schedule_auto()
    assert not h.svc.auto_check_pending


def test_an_automatic_check_finds_and_downloads_on_its_own(make: Make, qtbot: QtBot) -> None:
    script = Script(offer=found("1.2.0"))
    h = make(script, first_check_ms=10)
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)
    assert h.codes() == ["update.ready"]


# ---------------------------------------------------------------------------- skip and install


def test_skipping_a_ready_version_keeps_it_from_being_applied(make: Make) -> None:
    h = make(Script(pending=FakeAsset("1.2.0")))
    h.svc.skip("1.2.0")

    assert h.current.updates_skipped_version == "1.2.0"
    assert h.svc.snapshot().get("skipped") is True
    assert not h.svc.apply_on_exit
    h.svc.hand_over()
    assert "apply_after_exit" not in h.script.names()


def test_forgetting_the_skip_of_a_ready_version_applies_it_again(make: Make) -> None:
    h = make(Script(pending=FakeAsset("1.2.0")))
    h.svc.skip("1.2.0")
    h.svc.skip("")

    assert h.payloads[-1]["skipped"] is False
    assert h.svc.apply_on_exit
    h.svc.hand_over()
    assert h.script.names()[-1] == "apply_after_exit"


def test_a_skip_changed_in_the_settings_is_the_one_that_counts(make: Make) -> None:
    """updates_skipped_version is an ordinary setting, so updateSettings can change it too."""
    h = make(Script(pending=FakeAsset("1.2.0")))
    h.settings.append(replace(h.current, updates_skipped_version="1.2.0"))
    h.svc.settings_changed()

    assert h.payloads[-1]["skipped"] is True
    assert not h.svc.apply_on_exit
    h.svc.hand_over()
    assert "apply_after_exit" not in h.script.names()


def test_skip_refuses_what_is_not_a_version(make: Make) -> None:
    h = make()
    h.svc.skip("9" * 65)
    assert h.current.updates_skipped_version == ""


def test_a_skipped_ready_version_does_not_block_a_newer_check(make: Make, qtbot: QtBot) -> None:
    h = make(Script(pending=FakeAsset("1.2.0"), offer=found("1.3.0")))
    h.svc.skip("1.2.0")
    h.svc.check()
    qtbot.waitUntil(lambda: h.svc.snapshot().get("version") == "1.3.0", timeout=WAIT_MS)
    qtbot.waitUntil(lambda: h.svc.phase is Phase.READY, timeout=WAIT_MS)
    assert h.svc.apply_on_exit


def test_install_later_confirms_and_overrides_a_skip(make: Make) -> None:
    h = make(Script(pending=FakeAsset("1.2.0")), updates_skipped_version="1.2.0")
    assert not h.svc.apply_on_exit
    assert h.notices == []

    h.svc.install(False)

    assert h.current.updates_skipped_version == ""
    assert h.svc.apply_on_exit
    assert h.notices == [("info", "update.ready", {"version": "1.2.0"})]
    assert "apply_after_exit" not in h.script.names()  # not while the app runs
    h.svc.hand_over()
    assert h.script.names()[-1] == "apply_after_exit"


def test_restart_now_gets_everything_ready_before_handing_over(make: Make) -> None:
    journal: list[str] = []
    h = make(Script(pending=FakeAsset("1.2.0"), journal=journal))

    h.svc.install(True)

    assert journal == ["pending", "prepare_exit", "apply_restart"]
    restart = next(c for c in h.script.calls if c.name == "apply_restart")
    assert restart.thread != threading.get_ident()


def test_a_failed_restart_now_is_reported_and_can_be_retried(make: Make, qtbot: QtBot) -> None:
    h = make(Script(pending=FakeAsset("1.2.0"), apply_error=RuntimeError("Update.exe missing")))
    h.svc.install(True)
    settle(qtbot, h)

    assert h.svc.snapshot().get("stage") == "install"
    assert h.notices[-1] == ("error", "update.failed", {"reason": "Update.exe missing"})
    assert h.resumed == 1
    h.svc.check()  # would forget the downloaded release, which still waits for the exit
    assert "check" not in h.script.names()
    assert h.svc.apply_on_exit

    h.script.apply_error = None
    h.svc.install(True)
    assert h.script.names().count("apply_restart") == 2


def test_a_failure_getting_ready_stops_the_install(make: Make) -> None:
    def broken() -> None:
        raise OSError("disk gone")

    h = make(Script(pending=FakeAsset("1.2.0")), prepare_exit=broken)
    h.svc.install(True)

    assert "apply_restart" not in h.script.names()
    assert h.svc.snapshot().get("stage") == "install"
    assert h.resumed == 1  # it may have taken windows down before it failed


# ---------------------------------------------------------------------------- shutdown


def test_shutdown_leaves_a_stuck_worker_behind_without_waiting_long(
    make: Make, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service, "SHUTDOWN_WAIT_S", 0.05)
    gate = threading.Event()
    h = make(Script(offer=found("1.2.0"), gate=gate))
    h.svc.check()

    h.svc.close()
    before = list(h.payloads)
    gate.set()
    qtbot.wait(100)

    assert h.payloads == before  # a late outcome is not acted on
    h.svc.check()
    assert h.script.names().count("check") == 1


def test_closing_hands_nothing_over_and_hand_over_does_it_later(make: Make) -> None:
    """The window closes first; Update.exe is started only after the event loop is over."""
    h = make(Script(pending=FakeAsset("1.2.0")))
    h.svc.close()
    assert "apply_after_exit" not in h.script.names()

    h.svc.hand_over()
    h.svc.hand_over()
    assert h.script.names().count("apply_after_exit") == 1


def test_nothing_is_applied_at_exit_without_a_download(make: Make) -> None:
    h = make()
    h.svc.hand_over()
    assert "apply_after_exit" not in h.script.names()
