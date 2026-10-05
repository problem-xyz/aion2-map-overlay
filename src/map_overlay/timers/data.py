"""Which copy of the timers' data the app uses, and how a newer one gets in. No Qt.

Two files, the schedule and the world bosses, each in two places: the copy bundled with the
app, and one fetched later and kept under the data directory's cache. The newer of the two wins
-- by updatedAt for the schedule and readAt for the bosses, the fetched one on a tie -- so a
fetched copy outlives an app update only while it is still the newer one.

What the repository serves replaces the last fetched copy whatever its date: it is the
publisher's latest word, and a correction can move a reading back by a few seconds, or add a
field without a new reading at all. Only the bundled copy is a floor, so a stale file there
never undoes an app update. A fetched file is checked whole before it replaces anything; a
broken or foreign one is refused and the copy in use stays.

The network itself is a callable handed in, so this module can be tested without one and the
caller decides which thread it runs on.
"""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from map_overlay.core.appinfo import APP_NAME, TIMERS_DATA_URL
from map_overlay.core.fileio import atomic_write_bytes, atomic_write_json, read_json_or_none
from map_overlay.store.timers import (
    Schedule,
    TimersError,
    WorldBosses,
    bundled_schedule,
    bundled_world_bosses,
    parse_schedule,
    parse_world_bosses,
)

log = logging.getLogger(__name__)

Kind = Literal["schedule", "bosses"]
FILES: dict[Kind, str] = {"schedule": "schedule.json", "bosses": "world-bosses.json"}

# The schedule is a few kilobytes and the boss list about five: anything near this is not ours.
MAX_BYTES = 512 * 1024
TIMEOUT_S = 15


class FetchError(Exception):
    """The file could not be fetched; the message is for the log."""


@dataclass(frozen=True)
class Fetched:
    """What the network gave: a new body and its ETag, or nothing new (body None)."""

    body: bytes | None
    etag: str | None


# url, the ETag of the copy we hold (or None) -> what came back
Transport = Callable[[str, str | None], Fetched]


def http_transport(url: str, etag: str | None) -> Fetched:
    """A GET with If-None-Match, capped in size and time. Raises FetchError on any failure."""
    request = urllib.request.Request(url, headers={"User-Agent": APP_NAME.replace(" ", "")})
    if etag:
        request.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise FetchError(f"{url}: larger than {MAX_BYTES} bytes")
            return Fetched(body, response.headers.get("ETag"))
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return Fetched(None, etag)
        raise FetchError(f"{url}: HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(f"{url}: {e}") from e


@dataclass(frozen=True)
class TimersData:
    """The copies in use. Either may be None when neither copy of that file loads."""

    schedule: Schedule | None
    bosses: WorldBosses | None


class TimersStore:
    """The fetched copies under <cache>/timers/, and the choice between them and the bundled."""

    def __init__(self, cache_dir: Path, base_url: str = TIMERS_DATA_URL) -> None:
        self.dir = cache_dir / "timers"
        self.base_url = base_url

    def current(self) -> TimersData:
        return TimersData(schedule=self._schedule(), bosses=self._bosses())

    def refresh(self, kind: Kind, transport: Transport = http_transport) -> bool:
        """Fetch one file; True when a changed copy was taken in. Raises FetchError, TimersError.

        A body that does not parse, or is older than the bundled copy, is not written.
        """
        path = self.dir / FILES[kind]
        etags = self._etags()
        held = etags.get(kind) if path.is_file() else None
        got = transport(self.base_url + FILES[kind], held)
        if got.body is None:
            return False
        try:
            doc = json.loads(got.body)
        except ValueError as e:
            raise TimersError("timers.invalid", field="json") from e
        if kind == "schedule":
            fresh = parse_schedule(doc)
            bundled = bundled_schedule()
            older = bundled is not None and fresh.updated_at < bundled.updated_at
        else:
            fresh_bosses = parse_world_bosses(doc)
            bundled_bosses = bundled_world_bosses()
            older = bundled_bosses is not None and fresh_bosses.read_at < bundled_bosses.read_at
        if older:
            log.info("fetched timers %s is older than the copy bundled with the app", kind)
            return False
        same = path.is_file() and path.read_bytes() == got.body
        atomic_write_bytes(path, got.body)
        if got.etag:
            etags[kind] = got.etag
            atomic_write_json(self.dir / "etags.json", etags)
        if same:
            return False
        log.info("timers %s updated from %s", kind, self.base_url)
        return True

    def _schedule(self) -> Schedule | None:
        cached = self._cached(FILES["schedule"], parse_schedule)
        bundled = bundled_schedule()
        if cached is None or (bundled is not None and bundled.updated_at > cached.updated_at):
            return bundled
        return cached

    def _bosses(self) -> WorldBosses | None:
        cached = self._cached(FILES["bosses"], parse_world_bosses)
        bundled = bundled_world_bosses()
        if cached is None or (bundled is not None and bundled.read_at > cached.read_at):
            return bundled
        return cached

    def _cached[T](self, name: str, parse: Callable[[object], T]) -> T | None:
        doc = read_json_or_none(self.dir / name)
        if doc is None:
            return None
        try:
            return parse(doc)
        except TimersError as e:
            log.warning("cached timers file %s is not usable: %s", name, e)
            return None

    def _etags(self) -> dict[str, str]:
        doc = read_json_or_none(self.dir / "etags.json")
        if not isinstance(doc, dict):
            return {}
        return {str(k): str(v) for k, v in doc.items() if isinstance(v, str)}
