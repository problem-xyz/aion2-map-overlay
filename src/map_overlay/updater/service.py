"""The update state machine: when to check, what to download, and when to apply it.

The service, its state and its timer live on the GUI thread. Every Velopack call blocks, so each
operation runs on a worker thread (updater/worker.py), one at a time, and its outcome comes back
as a queued signal. The calls themselves are in updater/manager.py.

When an update is applied is set by what Update.exe does, read in Velopack 1.2.158's source:
wait_exit_then_apply_updates() starts `Update.exe apply --waitPid <this pid>`, which waits at most
60 s for this process (measured on an installed build) and then applies anyway, force-stopping
every process that runs from the install folder. Called while the app goes on running, straight
after an automatic download, it would kill the overlay a minute later, in the middle of a
game. So a downloaded update is only remembered, and handed over on the way out.

The wait on this process can also be denied outright (OpenProcess for SYNCHRONIZE fails, which
Velopack only logs), and then Update.exe applies at once and races the rest of the exit. So the
hand-over is as late as it can be: close() stops the updater when the window closes, and
hand_over() runs from main() after the event loop has ended and the settings are on disk.
"Restart now" (install(True)) saves and stops everything before its call too.
"""

import logging
from collections.abc import Callable
from dataclasses import replace
from enum import StrEnum
from typing import Any, NotRequired, Protocol, TypedDict

from PySide6.QtCore import QObject, QTimer, Signal

from map_overlay.core.settings import Settings
from map_overlay.updater import manager
from map_overlay.updater.feed import Feed, resolve_feed
from map_overlay.updater.manager import ManagerFactory, Release
from map_overlay.updater.worker import Op, Outcome, Worker, first_line

log = logging.getLogger(__name__)

FIRST_CHECK_DELAY_MS = 10_000
CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000
# Waits on the GUI thread, allowed only because the app is on its way out when they happen.
SHUTDOWN_WAIT_S = 2.0
APPLY_WAIT_S = 10.0

FAILED_CODE = "update.failed"


class Phase(StrEnum):
    """Where the updater stands. The value is what the page sees in `phase`."""

    DISABLED = "disabled"  # not a Velopack install: a source checkout or a copied dist
    IDLE = "idle"
    CHECKING = "checking"
    NONE = "none"  # the last check found nothing newer
    AVAILABLE = "available"
    DOWNLOADING = "downloading"
    READY = "ready"  # downloaded; applied when the app closes, or now on install(True)
    FAILED = "failed"


class UpdatePayload(TypedDict):
    """The update state as the page gets it: getState()["update"] and updateChanged.

    `version`, `notes` (Markdown) and `skipped` come with a known release; `progress` (0-100)
    only while downloading; `code`, `reason` and `stage` ("check", "download" or "install") only
    when failed, `code` being the notify code whose sentence fits.
    """

    phase: str
    version: NotRequired[str]
    notes: NotRequired[str]
    skipped: NotRequired[bool]
    progress: NotRequired[int]
    code: NotRequired[str]
    reason: NotRequired[str]
    stage: NotRequired[str]


class Notify(Protocol):
    def __call__(self, level: str, code: str, /, **params: Any) -> None: ...


class UpdaterService(QObject):
    """Checks for, downloads and applies updates; the page drives it through Backend's slots.

    GUI thread only. Each public method is a request: one that does not fit the current state
    -- a check while downloading, a second download, an install before anything is ready -- is
    logged and ignored, never queued and never raised. Failures of the network, the feed or
    Update.exe become the `failed` phase and an `update.failed` notice.

    Notices are `ready` and `failed` only, and an automatic `ready` comes at most once per version
    in a session. A version that is found has no notice of its own: the panel's update banner
    shows it. An automatic check that fails after another one failed is not announced again: a
    machine that is offline hears about it once, not every 6 hours.
    """

    stateChanged = Signal(dict)  # noqa: N815 -- Qt signal naming; the dict is an UpdatePayload

    def __init__(
        self,
        *,
        settings: Callable[[], Settings],
        update_settings: Callable[[dict[str, Any]], object],
        notify: Notify,
        prepare_exit: Callable[[], None],
        resume_after_failed_exit: Callable[[], None] | None = None,
        factory: ManagerFactory = manager.velopack_manager,
        feed: Feed | None = None,
        first_check_ms: int = FIRST_CHECK_DELAY_MS,
        interval_ms: int = CHECK_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._update_settings = update_settings
        self._notify = notify
        self._prepare_exit = prepare_exit
        self._resume = resume_after_failed_exit
        self._factory = factory
        self._feed = feed if feed is not None else resolve_feed()
        self._first_check_ms = first_check_ms
        self._interval_ms = interval_ms

        self._phase = Phase.DISABLED
        self._release: Release | None = None
        self._progress = 0
        self._failure: tuple[Op, str] | None = None
        self._auto = False  # the running operation was started by the timer, not the user
        self._auto_failing = False
        self._announced: set[tuple[str, str]] = set()
        self._closed = False

        self._worker = Worker(self)
        self._worker.done.connect(self._on_done)
        self._worker.progress.connect(self._on_progress)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timer)

    # ------------------------------------------------------------------ reading
    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def feed(self) -> Feed:
        return self._feed

    @property
    def auto_check_pending(self) -> bool:
        return self._timer.isActive()

    @property
    def busy(self) -> bool:
        """A worker's outcome is still to come."""
        return self._worker.busy

    @property
    def apply_on_exit(self) -> bool:
        """hand_over() will give a downloaded release to Update.exe.

        Worked out from the settings each time rather than kept, so that it can never disagree
        with `skipped` in the payload, whichever way the skipped version was changed.
        """
        release = self._release
        return release is not None and release.downloaded and not self._is_skipped(release)

    def snapshot(self) -> UpdatePayload:
        payload: UpdatePayload = {"phase": self._phase.value}
        release = self._release
        if release is not None and self._phase in (
            Phase.AVAILABLE,
            Phase.DOWNLOADING,
            Phase.READY,
            Phase.FAILED,
        ):
            payload["version"] = release.version
            payload["notes"] = release.notes
            payload["skipped"] = self._is_skipped(release)
        if self._phase is Phase.DOWNLOADING:
            payload["progress"] = self._progress
        if self._phase is Phase.FAILED and self._failure is not None:
            stage, reason = self._failure
            payload["code"] = FAILED_CODE
            payload["reason"] = reason
            payload["stage"] = stage.value
        return payload

    # ------------------------------------------------------------------ requests
    def start(self) -> None:
        """Find out whether this copy can update at all. Automatic checks follow if it can."""
        self._worker.run(Op.PROBE, lambda: manager.probe(self._factory, self._feed))

    def schedule_auto(self) -> None:
        """Arm the automatic check, 10 s from now and every 6 h after, or disarm it.

        Called once the probe has found an install, and again whenever updates_auto_check may
        have changed. A timer that is already running is left alone.
        """
        enabled = self._settings().updates_auto_check
        if self._closed or self._phase is Phase.DISABLED or not enabled:
            self._timer.stop()
            return
        if not self._timer.isActive():
            self._timer.start(self._first_check_ms)

    def check(self) -> None:
        """A check the user asked for."""
        self._check(auto=False)

    def download(self) -> None:
        """Download the release a check found; also the retry after a failed download."""
        release = self._release
        if not self._accepts("download", Phase.AVAILABLE, Phase.FAILED):
            return
        if release is None or release.downloaded:
            log.info("download ignored: no release to fetch")
            return
        if self._is_skipped(release):
            # Asking for a version the user once skipped is changing their mind about it.
            self._update_settings({"updates_skipped_version": ""})
        self._auto = False
        self._start_download(release)

    def install(self, restart: bool) -> None:
        """Apply the downloaded release: now, restarting the app, or when the app closes.

        install(False) is what happens anyway once a release is downloaded, so it only
        confirms that -- overriding a skip of this very version -- and says so. It never calls
        wait_exit_then_apply_updates() while the app runs (see the module docstring).

        install(True) saves and stops everything first, because Velopack ends the process
        inside the call: no `finally`, no atexit and no Qt teardown run after it.
        """
        release = self._release
        if self._closed or self.busy or release is None or not release.downloaded:
            log.info("install ignored while %s", self._worker.op or self._phase.value)
            return
        self._auto = False
        if self._is_skipped(release):
            self._update_settings({"updates_skipped_version": ""})
        if not restart:
            self._emit()
            self._announce("info", "update.ready", force=True, version=release.version)
            return

        log.info("installing %s now and restarting", release.version)
        try:
            self._prepare_exit()
        except Exception as e:
            log.exception("could not get ready to install the update")
            self._resume_after_failed_install()
            self._fail(Op.INSTALL, first_line(e))
            return
        for handler in logging.getLogger().handlers:
            handler.flush()
        thread = self._worker.run(
            Op.INSTALL, lambda: manager.apply_and_restart(self._factory, self._feed, release)
        )
        # Nothing may run between the flush above and the end of the process. Should the call
        # fail instead, its outcome is handled on the next turn of the event loop.
        if thread is not None:
            thread.join(APPLY_WAIT_S)

    def skip(self, version: str) -> None:
        """Remember a version not to offer again; an empty string forgets it."""
        if not isinstance(version, str) or len(version) > manager.MAX_VERSION_CHARS:
            log.info("skip ignored: not a version")
            return
        self._update_settings({"updates_skipped_version": version})
        self._emit()

    def settings_changed(self) -> None:
        """updates_skipped_version may have changed some other way: re-send the state."""
        if not self._closed:
            self._emit()

    def close(self) -> None:
        """The window is closing: no more checks, and let a running worker finish if it can.

        Nothing is handed to Update.exe here: that is hand_over(), once the event loop is over.
        """
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        if not self._worker.join(SHUTDOWN_WAIT_S):
            log.warning("update %s still running at exit; left behind", self._worker.op)

    def hand_over(self) -> None:
        """The last thing the app does: give a downloaded release to Update.exe, and return.

        main() calls it after the event loop has ended, when the settings are written, the
        engine is stopped and the single-instance lock is released. Update.exe is meant to wait
        for this process to exit, but that wait can be denied (measured: OpenProcess for
        SYNCHRONIZE failed, and it applied at once), so whatever runs after this call races it.
        The release is applied without starting the app again.
        """
        self.close()
        if not self._worker.join(0):
            return  # left behind by close(); a package on disk is found by the next run
        release = self._release
        if release is None or not self.apply_on_exit:
            return
        self._release = None  # given away: a second call has nothing to hand over
        log.info("update %s will be applied once the app has exited", release.version)
        for handler in logging.getLogger().handlers:
            handler.flush()
        self._worker.release()  # a finished job whose outcome will never be delivered now
        thread = self._worker.run(
            Op.EXIT, lambda: manager.apply_after_exit(self._factory, self._feed, release)
        )
        if thread is not None:
            thread.join(APPLY_WAIT_S)

    # ------------------------------------------------------------------ internals
    def _check(self, *, auto: bool) -> None:
        if self.apply_on_exit:
            # A check would drop the release it is holding for the exit; the next run checks.
            log.info("check ignored: a downloaded update waits for the app to close")
            return
        # READY here is a downloaded version the user skipped, which must not stop a newer one
        # from being found.
        allowed = (Phase.IDLE, Phase.NONE, Phase.AVAILABLE, Phase.FAILED, Phase.READY)
        if not self._accepts("check", *allowed):
            return
        self._auto = auto
        self._release = None
        self._set(Phase.CHECKING)
        self._worker.run(Op.CHECK, lambda: manager.check(self._factory, self._feed))

    def _start_download(self, release: Release) -> None:
        self._progress = 0
        self._set(Phase.DOWNLOADING)
        report = self._worker.report
        self._worker.run(
            Op.DOWNLOAD, lambda: manager.download(self._factory, self._feed, release, report)
        )

    def _accepts(self, what: str, *phases: Phase) -> bool:
        if self._closed or self.busy or self._phase not in phases:
            log.info("%s ignored while %s", what, self._worker.op or self._phase.value)
            return False
        return True

    def _on_done(self, outcome: Outcome) -> None:
        if self._closed:
            return
        if outcome.op is Op.PROBE:
            self._on_probe(outcome)
        elif outcome.error is not None:
            if outcome.op is Op.INSTALL:
                self._resume_after_failed_install()
            self._fail(outcome.op, outcome.error)
        elif outcome.op is Op.CHECK:
            self._on_checked(outcome.value)
        elif outcome.op is Op.DOWNLOAD:
            self._on_downloaded()
        elif outcome.op is Op.INSTALL:
            # Velopack ends the process when the call succeeds, so this is not expected. The
            # Update.exe it started all the same stops this process within about a minute.
            log.error("the update was handed over, but this process was not ended")

    def _on_progress(self, percent: int) -> None:
        if self._closed or self._phase is not Phase.DOWNLOADING:
            return
        percent = max(0, min(100, percent))
        if percent > self._progress:
            self._progress = percent
            self._emit()

    def _on_timer(self) -> None:
        if not self._settings().updates_auto_check:
            return
        self._timer.start(self._interval_ms)
        self._check(auto=True)

    def _on_probe(self, outcome: Outcome) -> None:
        if outcome.error is not None:
            return  # stays disabled; the worker has logged why
        release: Release | None = outcome.value
        if release is None:
            self._set(Phase.IDLE)
        else:
            # A previous run downloaded it and never got to apply it.
            self._release = release
            self._set(Phase.READY)
            if self.apply_on_exit:
                self._announce("info", "update.ready", version=release.version)
        self.schedule_auto()

    def _on_checked(self, release: Release | None) -> None:
        if self._auto:
            self._auto_failing = False
        if release is None:
            self._set(Phase.NONE)
            return
        self._release = release
        skipped = self._is_skipped(release)
        if skipped:
            log.info("version %s found; skipped, as the user asked", release.version)
        elif self._settings().updates_auto_download:
            self._start_download(release)
            return
        # No notice: the panel's update banner shows it, and a toast would appear in the same
        # window saying the same thing.
        self._set(Phase.AVAILABLE)

    def _on_downloaded(self) -> None:
        release = self._release
        if release is None:
            return
        release = replace(release, downloaded=True)
        self._release = release
        self._set(Phase.READY)
        if self.apply_on_exit:  # a skip made while it was downloading still stands
            self._announce("info", "update.ready", version=release.version)

    def _fail(self, op: Op, reason: str) -> None:
        self._failure = (op, reason)
        self._set(Phase.FAILED)
        if not self._auto:
            self._announce("error", FAILED_CODE, force=True, reason=reason)
        elif not self._auto_failing:
            self._auto_failing = True
            self._announce("warning", FAILED_CODE, force=True, reason=reason)

    def _resume_after_failed_install(self) -> None:
        """Bring back what prepare_exit took down; the app goes on running."""
        if self._resume is None:
            return
        try:
            self._resume()
        except Exception:
            log.exception("could not bring the app back after a failed install")

    def _is_skipped(self, release: Release) -> bool:
        return release.version == self._settings().updates_skipped_version

    def _announce(self, level: str, code: str, *, force: bool = False, **params: Any) -> None:
        key = (code, str(params.get("version", "")))
        if key in self._announced and not force:
            return
        self._announced.add(key)
        self._notify(level, code, **params)

    def _set(self, phase: Phase) -> None:
        if phase is not Phase.FAILED:
            self._failure = None
        self._phase = phase
        log.debug("update phase -> %s", phase.value)
        self._emit()

    def _emit(self) -> None:
        self.stateChanged.emit(dict(self.snapshot()))
