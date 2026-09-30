"""Backend.openUrl and copyText: the page asks, Python decides what reaches the browser."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from map_overlay.bridge.backend import Backend
from map_overlay.core.appinfo import DISCORD_URL, DONATE_URL, PARTNER_DISCORD_URL, REPO_URL
from map_overlay.core.paths import DataDirs
from map_overlay.store import banner as banner_store


@pytest.fixture
def backend(qapp: QApplication, dirs: DataDirs) -> Iterator[Backend]:
    made = Backend(dirs)
    try:
        yield made
    finally:
        made.shutdown()


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch, backend: Backend) -> list[str]:
    calls: list[str] = []

    def record(url: str) -> bool:
        calls.append(url)
        return True

    monkeypatch.setattr(backend._dialogs, "open_url", record)
    return calls


def test_release_notes_of_this_project_are_opened(backend: Backend, opened: list[str]) -> None:
    url = f"{REPO_URL}/releases/tag/v1.2.0"
    backend.openUrl(url)
    assert opened == [url]


def test_another_site_is_refused_and_logged(
    backend: Backend, opened: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    backend.openUrl("https://example.com/")
    assert opened == []
    assert any("refused" in r.getMessage() for r in caplog.records)


def test_get_state_names_the_repository(backend: Backend) -> None:
    assert json.loads(backend.getState())["repoUrl"] == REPO_URL


def test_get_state_names_the_support_links(backend: Backend) -> None:
    links = json.loads(backend.getState())["links"]
    assert links == {
        "donate": DONATE_URL,
        "discord": DISCORD_URL,
        "partnerDiscord": PARTNER_DISCORD_URL,
    }


@pytest.mark.parametrize("url", [REPO_URL, DONATE_URL, DISCORD_URL, PARTNER_DISCORD_URL])
def test_the_support_tiles_links_are_opened(backend: Backend, opened: list[str], url: str) -> None:
    backend.openUrl(url)
    assert opened == [url]


@pytest.fixture
def copied(monkeypatch: pytest.MonkeyPatch, backend: Backend) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(backend._dialogs, "copy", calls.append)
    return calls


def test_copy_text_puts_an_address_on_the_clipboard(backend: Backend, copied: list[str]) -> None:
    backend.copyText("bc1qxwfddau6a9dgmmels4nd82mdjzvmt05w02mkhf")
    assert copied == ["bc1qxwfddau6a9dgmmels4nd82mdjzvmt05w02mkhf"]


@pytest.mark.parametrize("text", ["", "x" * 257, None])
def test_copy_text_refuses_what_is_not_a_line(
    backend: Backend, copied: list[str], text: str
) -> None:
    backend.copyText(text)
    assert copied == []


def test_the_banner_s_page_is_opened_and_named_in_the_state(
    qapp: QApplication, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "banner"
    root.mkdir()
    (root / "banner.webp").write_bytes(b"\0")
    (root / "banner.json").write_text(
        json.dumps({"image": "banner.webp", "url": "https://example.com/ad", "label": "Ad"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(banner_store, "bundled_banner_root", lambda: root)
    made = Backend(dirs)
    try:
        calls: list[str] = []
        monkeypatch.setattr(made._dialogs, "open_url", lambda url: calls.append(url) or True)

        banner = json.loads(made.getState())["banner"]
        made.openUrl("https://example.com/ad")
        made.openUrl("https://example.com/other")
    finally:
        made.shutdown()

    assert banner["url"] == "https://example.com/ad"
    assert banner["label"] == "Ad"
    assert banner["image"].endswith("banner.webp")
    assert calls == ["https://example.com/ad"]


def test_with_no_banner_the_state_says_none(
    qapp: QApplication, dirs: DataDirs, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(banner_store, "bundled_banner_root", lambda: tmp_path)
    made = Backend(dirs)
    try:
        assert json.loads(made.getState())["banner"] is None
    finally:
        made.shutdown()
