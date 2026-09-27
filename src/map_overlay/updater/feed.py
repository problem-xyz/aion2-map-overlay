"""Where the updater looks for releases: UPDATE_URL, or an override kept for rehearsals.

The override lets an installed build be pointed at a local Releases folder, or at a staging
URL, so that an update can be rehearsed end to end without publishing anything. It is an
environment variable, read once when the updater is built, and nothing else: it is not a
setting, no file the app reads can carry it, and no slot sets it. A key in settings.json would
let anything that can drop a file redirect where the app downloads its code from; the
environment of a process is already in the hands of whoever starts it.

Only two shapes are accepted, an https URL and an existing local folder. Anything else is
logged and ignored, and the real feed is used, so a typo cannot quietly switch updates off.
"""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlsplit

from map_overlay.core.appinfo import UPDATE_URL

log = logging.getLogger(__name__)

OVERRIDE_ENV = "MAP_OVERLAY_UPDATE_URL"


class FeedKind(Enum):
    """How Velopack is to read the feed: over HTTP, or from a folder on this machine."""

    HTTP = "http"
    FOLDER = "folder"


@dataclass(frozen=True)
class Feed:
    """A release feed, resolved once and handed to every worker as it is."""

    kind: FeedKind
    location: str
    overridden: bool = False


DEFAULT_FEED = Feed(FeedKind.HTTP, UPDATE_URL)


def resolve_feed(environ: Mapping[str, str] | None = None) -> Feed:
    """The feed this process uses: UPDATE_URL unless MAP_OVERLAY_UPDATE_URL names a valid one."""
    env = os.environ if environ is None else environ
    raw = env.get(OVERRIDE_ENV, "").strip()
    if not raw:
        return DEFAULT_FEED
    feed = _parse_override(raw)
    if feed is None:
        log.warning(
            "%s=%r ignored: it has to be an https URL or an existing local folder; using %s",
            OVERRIDE_ENV,
            raw,
            UPDATE_URL,
        )
        return DEFAULT_FEED
    log.warning("update feed overridden by %s: %s", OVERRIDE_ENV, feed.location)
    return feed


def _parse_override(raw: str) -> Feed | None:
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    if scheme == "https":
        # Credentials in the URL would end up in the log line above and in Velopack's own.
        if not parts.hostname or parts.username is not None or parts.password is not None:
            return None
        return Feed(FeedKind.HTTP, raw, overridden=True)
    # A drive letter parses as a one-letter scheme; anything longer (http, file, ftp) is a URL.
    if len(scheme) > 1:
        return None
    # A UNC path is a folder on another machine, which is a feed nobody here can vouch for.
    if raw.startswith(("\\\\", "//")):
        return None
    path = Path(raw)
    if not path.is_absolute() or not path.is_dir():
        return None
    return Feed(FeedKind.FOLDER, str(path.resolve()), overridden=True)
