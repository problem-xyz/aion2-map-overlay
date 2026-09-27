"""Where updates come from, and the one way to point an installed copy somewhere else.

The override is for rehearsing an update against a local Releases folder. It is read from the
environment only, so the last two tests pin that neither settings.json nor updateSettings can
carry it: a key there would let anything that can write a file choose where the app downloads
its own code from.
"""

import json
import logging
from pathlib import Path

import pytest

from map_overlay.core.appinfo import UPDATE_URL
from map_overlay.core.paths import DataDirs
from map_overlay.core.settings import Settings, coerce
from map_overlay.updater.feed import DEFAULT_FEED, OVERRIDE_ENV, Feed, FeedKind, resolve_feed

LOGGER = "map_overlay.updater.feed"


def test_the_feed_is_the_latest_release_on_github_by_redirect() -> None:
    assert resolve_feed({}) == Feed(FeedKind.HTTP, UPDATE_URL)
    assert UPDATE_URL.startswith("https://github.com/")
    # latest/download/ is served by redirect, with no API call; the slash is where names go.
    assert UPDATE_URL.endswith("/releases/latest/download/")


def test_an_https_override_is_used_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    feed = resolve_feed({OVERRIDE_ENV: "https://example.org/staging/"})

    assert feed == Feed(FeedKind.HTTP, "https://example.org/staging/", overridden=True)
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_an_existing_local_folder_is_a_folder_feed(tmp_path: Path) -> None:
    feed = resolve_feed({OVERRIDE_ENV: f"  {tmp_path}  "})
    assert feed == Feed(FeedKind.FOLDER, str(tmp_path.resolve()), overridden=True)


@pytest.mark.parametrize(
    "value",
    [
        "http://example.org/releases/",  # not encrypted
        "file:///C:/Releases",
        "ftp://example.org/",
        "https://user:secret@example.org/",  # would be logged
        "https:///no-host",
        "Releases",  # relative
        r"\\server\share\Releases",  # not on this machine
        "//server/share/Releases",
    ],
)
def test_anything_else_is_ignored_with_a_warning(
    value: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)
    assert resolve_feed({OVERRIDE_ENV: value}) == DEFAULT_FEED
    assert any("ignored" in r.getMessage() for r in caplog.records)


def test_a_missing_folder_or_a_file_is_ignored(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    a_file = tmp_path / "releases.win.json"
    a_file.write_text("{}", encoding="utf-8")

    assert resolve_feed({OVERRIDE_ENV: str(missing)}) == DEFAULT_FEED
    assert resolve_feed({OVERRIDE_ENV: str(a_file)}) == DEFAULT_FEED


def test_an_empty_override_is_no_override() -> None:
    assert resolve_feed({OVERRIDE_ENV: "   "}) == DEFAULT_FEED


def test_settings_json_cannot_carry_a_feed(dirs: DataDirs) -> None:
    raw = {"update_url": "https://evil.example/", "MAP_OVERLAY_UPDATE_URL": "https://evil/"}
    settings, _ = coerce(raw, Settings)

    assert settings == Settings()
    assert not any("url" in name.lower() for name in Settings.__dataclass_fields__)
    dirs.settings.write_text(json.dumps({"version": 1, **raw}), encoding="utf-8")
    assert resolve_feed({}) == DEFAULT_FEED
