"""Announce one release on Discord: its CHANGELOG section as text, and buttons to download it.

    uv run python scripts/discord_announce.py 1.0.0-beta.1 --output announce.json
    uv run python scripts/discord_announce.py 1.0.0-beta.1 --role 123456789012345678 --post
    uv run python scripts/discord_announce.py 1.0.0-beta.0 --dry-run    # [Unreleased] if need be

The message is plain text, not an embed, with the downloads as link buttons under it. The
release workflow posts it once the release is published, to the English and the Russian
download channel. Each channel reads `.github/discord/<version>.<lang>.md` when there is one:
a short announcement written by hand before the release, shorter and plainer than the
CHANGELOG, in the same shape as a section of it. Without one, the English channel takes the
CHANGELOG section, and any other falls back to the English text with a warning.
The buttons are file names, so the message has no other words. The section is the one
scripts/release_notes.py takes, without the install notes the release page carries: the GitHub
button leads there. The downloads themselves are not attached: the installer is far past the
size Discord takes from a webhook.

Pictures of what is new go with the text: `.github/discord/<version>/<lang>/`, in the order of
their names, the English ones for a channel whose language has none. They are attached to the
one message, under the text and above the buttons, at most ten, as Discord allows.

Discord does not reflow text: a CHANGELOG entry wrapped at 100 columns would arrive as broken
lines, so each entry is joined back into one. A message holds at most 2000 characters; a longer
section is cut at an entry and ends with a link to the full notes.

`--post` sends it to the webhook in DISCORD_WEBHOOK. With DISCORD_BOT_TOKEN set as well, a bot
that may pin messages in that channel pins it, and unpins what the same webhook posted before,
so the channel's pins hold the newest release alone. A failed pin is a warning: the news is out.
Both come from the environment, never the command line, which other processes can read.

`--role` pings that role, and only that one: the mentions are limited to it, so an `@everyone`
that ended up in the CHANGELOG pings nobody. Exit status 1 when release_notes.py would refuse.
"""

import argparse
import importlib.util
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from map_overlay.core.appinfo import APP_NAME, PACK_ID, REPO_URL
from map_overlay.core.fileio import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
TRANSLATIONS = ROOT / ".github" / "discord"
RELEASE_NOTES = Path(__file__).with_name("release_notes.py")

API = "https://discord.com/api/v10"
# Discord refuses a request without one of this shape.
USER_AGENT = f"DiscordBot ({REPO_URL}, 1)"
CONTENT_LIMIT = 2000
# The link a cut message ends with, in its channel's language.
FULL_NOTES = {"en": "the full notes", "ru": "полные заметки"}  # allow-cyrillic: the Russian channel
# No link previews under the text: the buttons already say where each link goes.
SUPPRESS_EMBEDS = 1 << 2
ACTION_ROW, BUTTON, LINK_STYLE = 1, 2, 5

# What a webhook takes in one message, and the pictures it shows as pictures.
MAX_IMAGES = 10
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")

HEADING = re.compile(r"^#{1,6}\s+(.*)$")
ENTRY = re.compile(r"^\s*(?:[-*+]|\d+\.)\s")
ROLE_ID = re.compile(r"^[0-9]{17,20}$")

type Send = Callable[[str, str, dict[str, Any] | bytes | None, dict[str, str]], Any]


def _load_release_notes() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_notes", RELEASE_NOTES)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {RELEASE_NOTES}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_notes = _load_release_notes()


def release_url(version: str) -> str:
    return f"{REPO_URL}/releases/tag/v{version}"


def download_url(version: str, suffix: str) -> str:
    return f"{REPO_URL}/releases/download/v{version}/{PACK_ID}-win-{suffix}"


def discord_markdown(section: str) -> list[str]:
    """The section as Discord shows it: one line per entry, `###` headings, no blank runs."""
    blocks: list[str] = []
    for line in section.splitlines():
        heading = HEADING.match(line)
        if heading:
            blocks.append(f"### {heading.group(1).strip()}")
        elif not line.strip():
            if blocks and blocks[-1]:
                blocks.append("")
        elif ENTRY.match(line):
            # Kept indented, so that a nested entry stays nested.
            blocks.append(line.rstrip())
        elif not blocks or not blocks[-1] or blocks[-1].startswith("#"):
            blocks.append(line.strip())
        else:
            blocks[-1] = f"{blocks[-1]} {line.strip()}"
    while blocks and not blocks[-1]:
        blocks.pop()
    return blocks


def content(head: str, section: str, version: str, lang: str = "en") -> str:
    """`head`, then the section, cut at an entry when the two would not fit in one message."""
    lines = [head, "", *discord_markdown(section)]
    text = "\n".join(lines)
    if len(text) <= CONTENT_LIMIT:
        return text
    more = f"\n\n[... {FULL_NOTES[lang]}]({release_url(version)})"
    kept: list[str] = []
    for line in lines:
        if len("\n".join([*kept, line])) + len(more) > CONTENT_LIMIT:
            break
        kept.append(line)
    while len(kept) > 1 and (not kept[-1] or kept[-1].startswith("#")):
        kept.pop()
    return "\n".join(kept) + more


def link_button(label: str, url: str, emoji: str | None = None) -> dict[str, Any]:
    button: dict[str, Any] = {"type": BUTTON, "style": LINK_STYLE, "label": label, "url": url}
    if emoji:
        button["emoji"] = {"name": emoji}
    return button


def translated_section(version: str, lang: str, root: Path | None = None) -> str | None:
    """The section in `lang` from `<version>.<lang>.md`, or None when nobody wrote one."""
    try:
        text = ((root or TRANSLATIONS) / f"{version}.{lang}.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    return text.strip("\n") or None


def images(version: str, lang: str, root: Path | None = None) -> list[Path]:
    """The pictures for the `lang` channel, in name order: its own, or else the English ones."""
    base = (root or TRANSLATIONS) / version
    for folder in (base / lang, base / "en"):
        if folder.is_dir():
            found = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
            if found:
                return found[:MAX_IMAGES]
    return []


def form(message: dict[str, Any], files: Sequence[Path]) -> tuple[bytes, str]:
    """The message and its pictures as one multipart body, and the Content-Type that says so."""
    boundary = uuid.uuid4().hex
    payload = {
        **message,
        "attachments": [{"id": i, "filename": f.name} for i, f in enumerate(files)],
    }
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
        "Content-Type: application/json\r\n\r\n".encode()
        + json.dumps(payload).encode("utf-8")
        + b"\r\n"
    ]
    for i, f in enumerate(files):
        kind = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; '
            f'filename="{f.name}"\r\nContent-Type: {kind}\r\n\r\n'.encode()
            + f.read_bytes()
            + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def announcement(
    changelog: str,
    version: str,
    *,
    role: str | None = None,
    dry_run: bool = False,
    lang: str = "en",
    translation: str | None = None,
) -> dict[str, Any]:
    """The message for one channel: `translation`, in `lang`, when given, else the CHANGELOG's.

    The CHANGELOG section is read either way, so a version that was never cut is refused in
    every language alike.
    """
    try:
        section = release_notes.changelog_section(changelog, version)
    except release_notes.NotesError:
        if not dry_run:
            raise
        section = release_notes.changelog_section(changelog, "Unreleased")
    if translation is not None:
        section = translation
    else:
        lang = "en"
    title = f"## {APP_NAME} {version}"
    head = f"<@&{role}>\n{title}" if role else title
    return {
        "content": content(head, section, version, lang),
        "flags": SUPPRESS_EMBEDS,
        "components": [
            {
                "type": ACTION_ROW,
                "components": [
                    link_button("Setup.exe", download_url(version, "Setup.exe"), "⬇️"),
                    link_button("Portable.zip", download_url(version, "Portable.zip")),
                    link_button("GitHub", release_url(version)),
                ],
            }
        ],
        "allowed_mentions": {"parse": [], "roles": [role] if role else []},
    }


def _send(
    method: str, url: str, body: dict[str, Any] | bytes | None, headers: dict[str, str]
) -> Any:
    """A dict goes as JSON; bytes go as they are, with the Content-Type in `headers`."""
    if isinstance(body, bytes):
        data = body
    else:
        data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("User-Agent", USER_AGENT)
    if data is not None and "Content-Type" not in headers:
        request.add_header("Content-Type", "application/json")
    for name, value in headers.items():
        request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def post(
    message: dict[str, Any],
    webhook: str,
    bot_token: str | None = None,
    send: Send = _send,
    files: Sequence[Path] = (),
) -> str:
    """Post through the webhook, `files` attached, and pin it in place of the earlier ones."""

    def body(msg: dict[str, Any]) -> tuple[dict[str, Any] | bytes, dict[str, str]]:
        if not files:
            return msg, {}
        data, kind = form(msg, files)
        return data, {"Content-Type": kind}

    try:
        # Without with_components a webhook no application owns drops the buttons.
        sent = send("POST", f"{webhook}?wait=true&with_components=true", *body(message))
    except urllib.error.HTTPError as error:
        if error.code != 400:
            raise
        print("warning: the webhook refused the buttons (HTTP 400); text alone", file=sys.stderr)
        bare = {key: value for key, value in message.items() if key != "components"}
        sent = send("POST", f"{webhook}?wait=true", *body(bare))
    if not bot_token:
        print("note: DISCORD_BOT_TOKEN is not set, so the post is not pinned", file=sys.stderr)
        return sent["id"]
    auth = {"Authorization": f"Bot {bot_token}"}
    pins = f"{API}/channels/{sent['channel_id']}/messages/pins"
    try:
        # Pinned first: should the rest fail, the channel still pins a release.
        send("PUT", f"{pins}/{sent['id']}", None, auth)
        for item in send("GET", pins, None, auth)["items"]:
            old = item["message"]
            if old.get("webhook_id") == sent["webhook_id"] and old["id"] != sent["id"]:
                send("DELETE", f"{pins}/{old['id']}", None, auth)
    except urllib.error.HTTPError as error:
        print(f"warning: could not pin the post (HTTP {error.code})", file=sys.stderr)
    return sent["id"]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="discord_announce.py",
        description="Write, or post, the Discord message that announces a release.",
    )
    parser.add_argument("version", help="the version, without the leading v")
    parser.add_argument("--role", help="id of the role to ping; none when omitted or empty")
    parser.add_argument(
        "--lang",
        choices=sorted(FULL_NOTES),
        default="en",
        help="the channel's language: reads .github/discord/<version>.<lang>.md when there is one",
    )
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--output", "-o", type=Path, help="write here instead of to stdout")
    where.add_argument(
        "--post", action="store_true", help="post to DISCORD_WEBHOOK, pin with DISCORD_BOT_TOKEN"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="take [Unreleased] if the version has no section"
    )
    args = parser.parse_args(argv)
    role = args.role or None
    if role is not None and not ROLE_ID.match(role):
        print(f"refused: '{role}' is not a Discord role id", file=sys.stderr)
        return 1
    webhook = os.environ.get("DISCORD_WEBHOOK", "")
    if args.post and not webhook:
        print("refused: --post needs the webhook in DISCORD_WEBHOOK", file=sys.stderr)
        return 1
    # A channel reads its own <version>.<lang>.md, then the short English one, then the CHANGELOG.
    lang = args.lang
    translation = translated_section(args.version, lang)
    if translation is None and lang != "en":
        print(
            f"warning: no .github/discord/{args.version}.{lang}.md, "
            f"so the {lang} channel gets the English notes",
            file=sys.stderr,
        )
        lang = "en"
        translation = translated_section(args.version, lang)
    try:
        changelog = CHANGELOG.read_text(encoding="utf-8")
        message = announcement(
            changelog,
            args.version,
            role=role,
            dry_run=args.dry_run,
            lang=lang,
            translation=translation,
        )
    except release_notes.NotesError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    pictures = images(args.version, args.lang)
    if args.post:
        token = os.environ.get("DISCORD_BOT_TOKEN") or None
        print(f"posted {post(message, webhook, token, files=pictures)}")
        return 0
    for picture in pictures:  # on stderr: stdout is the JSON alone
        print(f"attached: {picture.relative_to(ROOT)}", file=sys.stderr)
    # Escaped to ASCII: a Windows console cannot print the arrow on the button.
    text = json.dumps(message, indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        atomic_write_bytes(args.output, text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
