"""Notifier: how a notice is logged, and when it is sent."""

import json
import logging

import pytest

from map_overlay.bridge.notifier import Notifier


def test_each_level_is_logged_at_its_own_level_and_info_not_at_all(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # The log is searched for ERROR when something went wrong; an error notice logged as a
    # warning is invisible to that search.
    notifier = Notifier(lambda payload: None)

    with caplog.at_level(logging.INFO, logger="map_overlay.bridge.notifier"):
        notifier.error("route.save_failed", reason="disk full")
        notifier.warning("settings.corrupt", backup="settings.json.broken-1")
        notifier.info("route.saved", name="Gold route")

    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.ERROR, "notify error: route.save_failed {'reason': 'disk full'}"),
        (logging.WARNING, "notify warning: settings.corrupt {'backup': 'settings.json.broken-1'}"),
    ]


def test_post_holds_a_notice_until_the_first_drain_and_sends_at_once_after_it() -> None:
    sent: list[str] = []
    notifier = Notifier(sent.append)

    notifier.post("warning", "route.file_skipped", file="first.json")
    assert sent == []

    notifier.drain()
    notifier.post("warning", "route.file_skipped", file="second.json")

    assert [json.loads(p)["params"]["file"] for p in sent] == ["first.json", "second.json"]
