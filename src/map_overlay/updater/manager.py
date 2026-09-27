"""The calls into Velopack, as the worker threads make them.

Everything here blocks -- on the network, on disk, or on Update.exe -- and runs on a worker
thread, never on the GUI thread. Nothing here touches Qt or the service's state: a job gets a
factory and a feed, and returns a value or raises.

Each job builds its own UpdateManager. That is about a millisecond (it reads the install's
manifest and nothing else), it lets a check and a download carry different timeouts, and it
means no manager is ever used by two threads: two calls into one manager at once fail with
"Already borrowed" (measured with velopack 1.2.158). UpdateInfo and VelopackAsset are plain
data and were measured safe to hand from one thread to another.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import velopack

from map_overlay.updater.feed import Feed, FeedKind

log = logging.getLogger(__name__)

# The feed is a few hundred bytes (0.39 s against a real GitHub release). Without a
# timeout Velopack waits on a stalled connection for ever.
CHECK_TIMEOUT_MS = 30_000
# Velopack's timeout covers the whole request, transfer included, and a full package is about
# 200 MiB: generous enough for a slow line, finite so a dead one does not hold the worker for good.
DOWNLOAD_TIMEOUT_MS = 30 * 60_000

# Remote data ends up in the state payload on every getState(); release notes are a CHANGELOG
# section, and anything far larger than that is not worth carrying to the page.
MAX_NOTES_CHARS = 16_000
MAX_VERSION_CHARS = 64


class NotInstalledError(Exception):
    """This copy was not installed by Velopack: a source checkout or a copied dist folder."""


class UpdateManagerLike(Protocol):
    """The part of velopack.UpdateManager the updater uses. Tests stand a fake in for it."""

    def get_update_pending_restart(self) -> Any: ...

    def check_for_updates(self) -> Any: ...

    def download_updates(self, update_info: Any, progress_callback: Any | None = None) -> None: ...

    def apply_updates_and_restart(self, update: Any) -> None: ...

    def wait_exit_then_apply_updates(
        self,
        update: Any,
        silent: bool = False,
        restart: bool = True,
        restart_args: Sequence[str] | None = None,
    ) -> None: ...


ManagerFactory = Callable[[Feed, int], UpdateManagerLike]


@dataclass(frozen=True)
class Release:
    """A version the feed offers, or one already downloaded.

    `handle` is Velopack's own object for it, an UpdateInfo from a check or a VelopackAsset for
    a package already on disk, kept to be handed back to Velopack unchanged.
    """

    version: str
    notes: str
    handle: Any
    downloaded: bool = False


def velopack_manager(feed: Feed, timeout_ms: int) -> UpdateManagerLike:
    """A real UpdateManager for this install. Raises RuntimeError outside a Velopack install.

    The HTTP feed is always an explicit HttpSource: a plain string would be guessed at, and one
    on github.com is guessed to be a repository and sent to GitHub's API.
    """
    source: velopack.HttpSource | str
    if feed.kind is FeedKind.HTTP:
        source = velopack.HttpSource(feed.location, velopack.HttpOptions([], timeout_ms))
    else:
        source = feed.location
    return velopack.UpdateManager(source)


def _manager(factory: ManagerFactory, feed: Feed, timeout_ms: int) -> UpdateManagerLike:
    try:
        return factory(feed, timeout_ms)
    except RuntimeError as e:
        # Velopack has no exception type of its own, and its constructor fails on one thing only:
        # finding the install and reading its manifest (new_boxed in lib-rust's manager.rs). It
        # has not touched the feed by then.
        raise NotInstalledError(str(e)) from e


def release_of(found: Any, *, downloaded: bool = False) -> Release:
    """Read an UpdateInfo or a VelopackAsset into a Release."""
    asset = getattr(found, "TargetFullRelease", found)
    return Release(
        version=str(asset.Version)[:MAX_VERSION_CHARS],
        notes=str(asset.NotesMarkdown or "")[:MAX_NOTES_CHARS],
        handle=found,
        downloaded=downloaded,
    )


def probe(factory: ManagerFactory, feed: Feed) -> Release | None:
    """Whether this copy can update, and a package a previous run downloaded but never applied."""
    pending = _manager(factory, feed, CHECK_TIMEOUT_MS).get_update_pending_restart()
    return release_of(pending, downloaded=True) if pending is not None else None


def check(factory: ManagerFactory, feed: Feed) -> Release | None:
    """The newest release above the running version, or None."""
    found = _manager(factory, feed, CHECK_TIMEOUT_MS).check_for_updates()
    return release_of(found) if found is not None else None


def download(
    factory: ManagerFactory, feed: Feed, release: Release, report: Callable[[int], None]
) -> None:
    """Fetch the release into packages\\, a delta when there is one.

    `report` is called with a percentage on this same thread. A package already on disk is not
    fetched again, and then `report` is never called.
    """
    _manager(factory, feed, DOWNLOAD_TIMEOUT_MS).download_updates(release.handle, report)


def apply_and_restart(factory: ManagerFactory, feed: Feed, release: Release) -> None:
    """Hand the package to Update.exe and end this process. Returns only if that failed.

    Velopack ends the process inside the call (std::process::exit, measured), so
    `finally` blocks and atexit handlers do not run: whatever must reach the disk has to have
    done so already.
    """
    _manager(factory, feed, CHECK_TIMEOUT_MS).apply_updates_and_restart(release.handle)


def apply_after_exit(factory: ManagerFactory, feed: Feed, release: Release) -> None:
    """Start Update.exe to apply the package once this process has exited, and return.

    Only ever called on the way out: Update.exe waits at most 60 s for this process, and then
    applies anyway, killing whatever still runs from the install folder. The wait itself can be
    denied (OpenProcess for SYNCHRONIZE, measured), and then it applies at once, racing the rest
    of this process's exit.
    """
    manager = _manager(factory, feed, CHECK_TIMEOUT_MS)
    manager.wait_exit_then_apply_updates(release.handle, silent=True, restart=False)
