"""A stand-in for velopack.UpdateManager, scripted per test, that records what it was asked.

The real one needs a Velopack install to exist at all -- outside one its constructor raises --
and a feed to talk to, so the service's own logic is driven against this instead. The fake keeps
to the parts of the real API the updater uses, with the same parameter names, and its failures
are what Velopack's are: a RuntimeError with Velopack's wording. Each call is journalled with the
thread it ran on, which is what the threading tests read.
"""

import threading
from dataclasses import dataclass, field
from typing import Any

from map_overlay.updater.feed import Feed
from map_overlay.updater.manager import ManagerFactory, UpdateManagerLike

NOT_INSTALLED = "This application is not properly installed: Could not auto-locate app manifest"
TIMEOUT = "Network error: Http error: timeout: global"

# A gate the tests forget to open must not hang the run.
GATE_CEILING_S = 20.0


@dataclass
class FakeAsset:
    """VelopackAsset's two fields the updater reads, under Velopack's own PascalCase names."""

    Version: str
    NotesMarkdown: str = ""


@dataclass
class FakeInfo:
    """UpdateInfo, as far as the updater looks into it."""

    TargetFullRelease: FakeAsset


def found(version: str, notes: str = "") -> FakeInfo:
    return FakeInfo(FakeAsset(version, notes))


@dataclass
class Call:
    name: str
    thread: int
    args: tuple[Any, ...] = ()


@dataclass
class Script:
    """What every manager the factory builds will do. Tests change it between steps."""

    installed: bool = True
    pending: FakeAsset | None = None
    offer: FakeInfo | None = None
    check_error: BaseException | None = None
    download_error: Exception | None = None
    apply_error: Exception | None = None
    progress: list[int] = field(default_factory=lambda: [0, 70, 100])
    gate: threading.Event | None = None
    calls: list[Call] = field(default_factory=list)
    timeouts: list[int] = field(default_factory=list)
    journal: list[str] | None = None  # shared with the test's own recorders, for ordering

    def names(self) -> list[str]:
        return [c.name for c in self.calls]

    def record(self, name: str, *args: Any) -> None:
        self.calls.append(Call(name, threading.get_ident(), args))
        if self.journal is not None:
            self.journal.append(name)

    def wait_gate(self) -> None:
        if self.gate is not None:
            self.gate.wait(GATE_CEILING_S)


class FakeManager:
    def __init__(self, script: Script) -> None:
        self._script = script

    def get_update_pending_restart(self) -> Any:
        self._script.record("pending")
        return self._script.pending

    def check_for_updates(self) -> Any:
        self._script.record("check")
        self._script.wait_gate()
        if self._script.check_error is not None:
            raise self._script.check_error
        return self._script.offer

    def download_updates(self, update_info: Any, progress_callback: Any | None = None) -> None:
        self._script.record("download", update_info)
        self._script.wait_gate()
        if progress_callback is not None:
            for percent in self._script.progress:
                progress_callback(percent)
        if self._script.download_error is not None:
            raise self._script.download_error

    def apply_updates_and_restart(self, update: Any) -> None:
        self._script.record("apply_restart", update)
        if self._script.apply_error is not None:
            raise self._script.apply_error

    def wait_exit_then_apply_updates(
        self,
        update: Any,
        silent: bool = False,
        restart: bool = True,
        restart_args: Any = None,
    ) -> None:
        self._script.record("apply_after_exit", update, silent, restart)


def factory_for(script: Script) -> ManagerFactory:
    def make(feed: Feed, timeout_ms: int) -> UpdateManagerLike:
        script.timeouts.append(timeout_ms)
        if not script.installed:
            raise RuntimeError(NOT_INSTALLED)
        return FakeManager(script)

    return make
