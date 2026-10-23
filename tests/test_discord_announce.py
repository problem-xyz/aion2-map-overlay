"""scripts/discord_announce.py, the webhook message the release workflow posts to Discord.

Loaded by path, as test_release_notes.py loads its scripts.
"""

import importlib.util
import json
import re
import urllib.error
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from map_overlay.core.appinfo import APP_NAME, PACK_ID, REPO_URL

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


announce = load_script(REPO / "scripts" / "discord_announce.py", "discord_announce")

CHANGELOG = """\
# Changelog

## [Unreleased]

### Added

- Not released yet.

## [1.0.0-beta.1] - 2026-10-01

### Added

- A first entry, wrapped at the column limit
  onto a second line.
- A second one, with @everyone in it.
  - A nested one.

### Fixed

- Something from before.

[unreleased]: https://example.invalid/compare/v1.0.0-beta.1...HEAD
"""


HEAD = f"## {APP_NAME} 1.0.0-beta.1"
SECTION = (
    "### Added\n\n"
    "- A first entry, wrapped at the column limit onto a second line.\n"
    "- A second one, with @everyone in it.\n"
    "  - A nested one.\n\n"
    "### Fixed\n\n"
    "- Something from before."
)


def test_the_message_is_the_section_as_text_with_a_button_for_each_download() -> None:
    message = announce.announcement(CHANGELOG, "1.0.0-beta.1")
    assert message["content"] == f"{HEAD}\n\n{SECTION}"
    assert message["flags"] == announce.SUPPRESS_EMBEDS
    (row,) = message["components"]
    urls = [button["url"] for button in row["components"]]
    assert urls == [
        f"{REPO_URL}/releases/download/v1.0.0-beta.1/{PACK_ID}-win-Setup.exe",
        f"{REPO_URL}/releases/download/v1.0.0-beta.1/{PACK_ID}-win-Portable.zip",
        f"{REPO_URL}/releases/tag/v1.0.0-beta.1",
    ]
    assert all(button["style"] == announce.LINK_STYLE for button in row["components"])


def test_nobody_is_pinged_without_a_role_and_only_the_role_with_one() -> None:
    quiet = announce.announcement(CHANGELOG, "1.0.0-beta.1")
    assert quiet["content"].startswith(HEAD)
    assert quiet["allowed_mentions"] == {"parse": [], "roles": []}

    role = "123456789012345678"
    loud = announce.announcement(CHANGELOG, "1.0.0-beta.1", role=role)
    assert loud["content"].startswith(f"<@&{role}>\n{HEAD}\n")
    assert loud["allowed_mentions"] == {"parse": [], "roles": [role]}


def test_a_long_section_is_cut_at_an_entry_and_links_the_full_notes() -> None:
    entries = "\n".join(f"- Entry {i} " + "x" * 90 for i in range(100))
    changelog = CHANGELOG.replace("- Something from before.", entries)
    text = announce.announcement(changelog, "1.0.0-beta.1")["content"]
    assert len(text) <= announce.CONTENT_LIMIT
    body, more = text.rsplit("\n\n", 1)
    assert more == f"[... the full notes]({REPO_URL}/releases/tag/v1.0.0-beta.1)"
    assert body.startswith(HEAD)
    assert body.splitlines()[-1].startswith("- Entry ")
    assert body.splitlines()[-1].endswith("x" * 90)


def test_a_version_without_a_section_is_refused_unless_it_is_a_dry_run() -> None:
    with pytest.raises(announce.release_notes.NotesError, match=re.escape("no section for 2.0.0")):
        announce.announcement(CHANGELOG, "2.0.0")
    dry = announce.announcement(CHANGELOG, "2.0.0", dry_run=True)
    assert dry["content"] == f"## {APP_NAME} 2.0.0\n\n### Added\n\n- Not released yet."


WEBHOOK = "https://discord.com/api/webhooks/1/abc"
PINS = f"{announce.API}/channels/7/messages/pins"


class FakeDiscord:
    """Records the calls, answers with a post and the pins, and fails what it is told to."""

    def __init__(self, pinned: list[dict[str, Any]], fail: dict[str, int] | None = None) -> None:
        self.pinned = pinned
        self.fail = fail or {}
        self.calls: list[tuple[str, str, dict[str, Any] | bytes | None, dict[str, str]]] = []

    def __call__(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | bytes | None,
        headers: dict[str, str],
    ) -> Any:
        self.calls.append((method, url, body, headers))
        code = self.fail.get(f"{method} {url}")
        if code:
            raise urllib.error.HTTPError(url, code, "refused", Message(), None)
        if method == "POST":
            return {"id": "100", "channel_id": "7", "webhook_id": "1"}
        if method == "GET":
            return {"items": [{"message": m} for m in self.pinned], "has_more": False}
        return None


def test_the_post_is_pinned_and_the_webhook_s_earlier_pins_let_go() -> None:
    discord = FakeDiscord(
        [{"id": "100", "webhook_id": "1"}, {"id": "90", "webhook_id": "1"}, {"id": "5"}]
    )
    assert announce.post({"content": "x"}, WEBHOOK, "token", send=discord) == "100"
    assert [(method, url) for method, url, _, _ in discord.calls] == [
        ("POST", f"{WEBHOOK}?wait=true&with_components=true"),
        ("PUT", f"{PINS}/100"),
        ("GET", PINS),
        # A pin made by hand, message 5, stays.
        ("DELETE", f"{PINS}/90"),
    ]
    assert all(h == {"Authorization": "Bot token"} for _, _, _, h in discord.calls[1:])


def test_without_a_bot_token_the_post_goes_out_unpinned() -> None:
    discord = FakeDiscord([])
    assert announce.post({"content": "x"}, WEBHOOK, None, send=discord) == "100"
    assert [method for method, _, _, _ in discord.calls] == ["POST"]


def test_refused_buttons_leave_the_text_and_a_refused_pin_only_warns(
    capsys: pytest.CaptureFixture[str],
) -> None:
    fail = {f"POST {WEBHOOK}?wait=true&with_components=true": 400, f"PUT {PINS}/100": 403}
    discord = FakeDiscord([], fail)
    message = {"content": "x", "components": [{"type": 1}]}
    assert announce.post(message, WEBHOOK, "token", send=discord) == "100"
    method, url, body, _ = discord.calls[1]
    assert (method, url, body) == ("POST", f"{WEBHOOK}?wait=true", {"content": "x"})
    err = capsys.readouterr().err
    assert "refused the buttons" in err
    assert "could not pin the post (HTTP 403)" in err


def test_the_command_writes_json_or_refuses_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(announce, "CHANGELOG", changelog)
    out = tmp_path / "announce.json"

    # An empty --role is how the workflow passes an unset variable.
    assert announce.main(["1.0.0-beta.1", "--role", "", "--output", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written == announce.announcement(CHANGELOG, "1.0.0-beta.1")

    missing = tmp_path / "missing.json"
    assert announce.main(["2.0.0", "--output", str(missing)]) == 1
    assert announce.main(["1.0.0-beta.1", "--role", "@Updates", "--output", str(missing)]) == 1
    assert not missing.exists()
    err = capsys.readouterr().err
    assert "refused: CHANGELOG.md has no section for 2.0.0" in err
    assert "'@Updates' is not a Discord role id" in err


def test_post_needs_the_webhook_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("DISCORD_WEBHOOK", raising=False)
    assert announce.main(["1.0.0-beta.1", "--dry-run", "--post"]) == 1
    assert "needs the webhook in DISCORD_WEBHOOK" in capsys.readouterr().err


# Stands in for the Russian text: tests stay free of Cyrillic (scripts/check_no_cyrillic.py).
TRANSLATION = "### Fixed (ru)\n\n- The same fix, translated,\n  over two lines."


def test_a_translation_takes_the_place_of_the_section() -> None:
    message = announce.announcement(CHANGELOG, "1.0.0-beta.1", lang="ru", translation=TRANSLATION)

    assert (
        message["content"]
        == f"{HEAD}\n\n### Fixed (ru)\n\n- The same fix, translated, over two lines."
    )
    assert message["components"] == announce.announcement(CHANGELOG, "1.0.0-beta.1")["components"]


def test_a_translation_does_not_let_an_uncut_version_through() -> None:
    with pytest.raises(announce.release_notes.NotesError):
        announce.announcement(CHANGELOG, "2.0.0", lang="ru", translation=TRANSLATION)


def test_a_long_translation_links_the_full_notes_in_its_own_language() -> None:
    long = "\n".join(f"- Entry {i} " + "x" * 90 for i in range(100))
    text = announce.announcement(CHANGELOG, "1.0.0-beta.1", lang="ru", translation=long)["content"]

    assert len(text) <= announce.CONTENT_LIMIT
    assert text.endswith(
        f"[... {announce.FULL_NOTES['ru']}]({REPO_URL}/releases/tag/v1.0.0-beta.1)"
    )


def test_the_command_reads_the_translation_or_falls_back_to_english(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(announce, "CHANGELOG", changelog)
    monkeypatch.setattr(announce, "TRANSLATIONS", tmp_path)
    out = tmp_path / "announce.json"

    assert announce.main(["1.0.0-beta.1", "--lang", "ru", "--output", str(out)]) == 0
    english = announce.announcement(CHANGELOG, "1.0.0-beta.1")
    assert json.loads(out.read_text(encoding="utf-8")) == english
    assert "the ru channel gets the English notes" in capsys.readouterr().err

    (tmp_path / "1.0.0-beta.1.ru.md").write_text(f"\n{TRANSLATION}\n", encoding="utf-8")
    assert announce.main(["1.0.0-beta.1", "--lang", "ru", "--output", str(out)]) == 0
    translated = announce.announcement(
        CHANGELOG, "1.0.0-beta.1", lang="ru", translation=TRANSLATION
    )
    assert json.loads(out.read_text(encoding="utf-8")) == translated
    assert capsys.readouterr().err == ""


def test_a_short_english_text_replaces_the_changelog_and_is_the_fallback_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(announce, "CHANGELOG", changelog)
    monkeypatch.setattr(announce, "TRANSLATIONS", tmp_path)
    short = "### New\n\n- One short line."
    (tmp_path / "1.0.0-beta.1.en.md").write_text(short, encoding="utf-8")
    out = tmp_path / "announce.json"
    expected = announce.announcement(CHANGELOG, "1.0.0-beta.1", translation=short)

    assert announce.main(["1.0.0-beta.1", "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == expected
    assert capsys.readouterr().err == ""

    # A channel with no text of its own gets the short English one, not the CHANGELOG.
    assert announce.main(["1.0.0-beta.1", "--lang", "ru", "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8")) == expected
    assert "the ru channel gets the English notes" in capsys.readouterr().err


def test_every_translation_in_the_repository_is_one_the_script_can_post() -> None:
    for path in sorted((REPO / ".github" / "discord").glob("*.md")):
        version, lang, _ = path.name.rsplit(".", 2)
        assert lang in announce.FULL_NOTES, path.name
        text = announce.translated_section(version, lang)
        assert text is not None and text.startswith("### "), path.name
        head = f"## {APP_NAME} {version}"
        assert len(announce.content(head, text, version, lang)) <= announce.CONTENT_LIMIT


# ------------------------------------------------------------------ pictures


def test_the_pictures_are_the_channel_s_own_in_name_order_else_the_english(
    tmp_path: Path,
) -> None:
    en = tmp_path / "1.0.0" / "en"
    en.mkdir(parents=True)
    for name in ("2-b.jpg", "1-a.png", "notes.txt"):
        (en / name).write_bytes(b"x")

    assert [p.name for p in announce.images("1.0.0", "en", tmp_path)] == ["1-a.png", "2-b.jpg"]
    assert [p.name for p in announce.images("1.0.0", "ru", tmp_path)] == ["1-a.png", "2-b.jpg"]
    ru = tmp_path / "1.0.0" / "ru"
    ru.mkdir()
    (ru / "1-a.png").write_bytes(b"x")
    assert [p.name for p in announce.images("1.0.0", "ru", tmp_path)] == ["1-a.png"]
    assert announce.images("2.0.0", "en", tmp_path) == []


def test_pictures_go_in_one_multipart_message_with_the_text_and_the_buttons(
    tmp_path: Path,
) -> None:
    picture = tmp_path / "1-cubes.jpg"
    picture.write_bytes(b"\xff\xd8jpeg")
    discord = FakeDiscord([])
    message = {"content": "x", "components": [{"type": 1}]}

    announce.post(message, WEBHOOK, None, send=discord, files=[picture])

    _method, _url, body, headers = discord.calls[0]
    assert isinstance(body, bytes)
    boundary = headers["Content-Type"].split("boundary=")[1]
    parts = body.split(f"--{boundary}".encode())
    payload = json.loads(parts[1].split(b"\r\n\r\n", 1)[1])
    assert payload["content"] == "x"
    assert payload["components"] == [{"type": 1}]
    assert payload["attachments"] == [{"id": 0, "filename": "1-cubes.jpg"}]
    assert b'name="files[0]"; filename="1-cubes.jpg"' in parts[2]
    assert b"Content-Type: image/jpeg" in parts[2]
    assert parts[2].endswith(b"\xff\xd8jpeg\r\n")


def test_refused_buttons_still_take_the_pictures(tmp_path: Path) -> None:
    picture = tmp_path / "1-cubes.jpg"
    picture.write_bytes(b"jpeg")
    discord = FakeDiscord([], {f"POST {WEBHOOK}?wait=true&with_components=true": 400})
    message = {"content": "x", "components": []}

    announce.post(message, WEBHOOK, None, send=discord, files=[picture])

    _method, _url, body, _headers = discord.calls[1]
    assert isinstance(body, bytes)
    assert b'filename="1-cubes.jpg"' in body
    assert b'"components"' not in body


def test_every_picture_in_the_repository_is_one_discord_shows() -> None:
    for folder in sorted((REPO / ".github" / "discord").glob("*/*/")):
        found = announce.images(folder.parent.name, folder.name)
        assert 0 < len(found) <= announce.MAX_IMAGES, folder
        # Discord takes 10 MB a message from a webhook on a server without boosts.
        assert sum(p.stat().st_size for p in found) < 8_000_000, folder
