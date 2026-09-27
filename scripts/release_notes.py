"""Write the notes of one release: its CHANGELOG section, then how to install it.

    uv run python scripts/release_notes.py 1.0.0-beta.1 --output release-notes.md
    uv run python scripts/release_notes.py 1.0.0-beta.0 --dry-run    # [Unreleased] if need be

`vpk pack --releaseNotes` stores the file in the package, and `vpk upload github` makes it the
body of the GitHub release, so this is what a user reads on the release page. The section is
the one scripts/bump_version.py dated, `## [<version>] - <date>`, taken as written (Keep a
Changelog 1.1.0) without its heading, which the release's name repeats. What follows it is the
same for every release: which file to download, the SmartScreen warning an unsigned installer
gets, and where the third-party licences are.

Exit status 1, with nothing written, when CHANGELOG.md has no section for the version or the
section is empty: a release without notes is a release nobody can tell apart from the last.
`--dry-run` is for the release workflow's dry run, which packs a version that has not been cut:
without a section for it, the notes take `[Unreleased]` instead.
"""

import argparse
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from map_overlay.core.appinfo import APP_DIR_NAME, APP_NAME, PACK_ID
from map_overlay.core.fileio import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

SECTION_HEADING = re.compile(r"^## ")
LINK_DEFINITION = re.compile(r"^\[[^\]]+\]:\s*\S+\s*$")


class NotesError(Exception):
    """The notes cannot be written; the message says why."""


def changelog_section(text: str, version: str) -> str:
    """The body of `## [version]` in a Keep a Changelog file, without its heading."""
    heading = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s|$)")
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if heading.match(line)]
    if not starts:
        raise NotesError(
            f"CHANGELOG.md has no section for {version}: scripts/bump_version.py {version} "
            "writes it when it cuts the release"
        )
    if len(starts) > 1:
        raise NotesError(f"CHANGELOG.md has {len(starts)} sections for {version}")
    start = starts[0] + 1
    end = next((i for i in range(start, len(lines)) if SECTION_HEADING.match(lines[i])), len(lines))
    # The last section runs into the file's link definitions, which belong to no release.
    body = [line for line in lines[start:end] if not LINK_DEFINITION.match(line)]
    if not any(line.strip() and not line.lstrip().startswith("#") for line in body):
        raise NotesError(f"the section for {version} in CHANGELOG.md is empty")
    return "\n".join(body).strip("\n")


def install_notes() -> str:
    """How to install, the SmartScreen warning and where the licences are, for every release."""
    return f"""\
## How to install

- **Installer (recommended):** download and run
  `{PACK_ID}-win-Setup.exe`. It installs for your Windows account only, without
  administrator rights, and adds shortcuts. Uninstall it from *Settings > Apps* like any other
  program. An installed copy keeps your maps, routes and settings in
  `%LocalAppData%\\{APP_DIR_NAME}`, which uninstalling leaves in place.
- **Portable:** download `{PACK_ID}-win-Portable.zip`, extract it to a folder
  of your choice and run `{APP_NAME}.exe` there. That copy keeps its maps, routes and settings
  in a `userdata` folder beside it; only its launcher writes a log to `%LocalAppData%\\velopack`.

The other files attached to this release are for updating an installed copy; you do not need
them.

### "Windows protected your PC"

The installer is not code-signed yet, so Windows SmartScreen may stop it the first time. Click
**More info**, check that the app is
`{PACK_ID}-win-Setup.exe`, then **Run anyway**.

### Third-party licences

The app includes software by others, each under its own licence. Their texts, with where to get
the source of the LGPL parts, are in the `THIRD-PARTY-NOTICES` folder next to `{APP_NAME}.exe`:
in `current\\` inside the install folder or the portable folder. The installer and the updater,
`Setup.exe` and `Update.exe`, are Velopack's; their licences are in
`THIRD-PARTY-NOTICES\\velopack`.
"""


def release_notes(changelog: str, version: str, *, dry_run: bool = False) -> str:
    try:
        section = changelog_section(changelog, version)
    except NotesError:
        if not dry_run:
            raise
        section = changelog_section(changelog, "Unreleased")
    return f"{section}\n\n{install_notes()}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="release_notes.py",
        description="Write a release's notes from its CHANGELOG.md section.",
    )
    parser.add_argument("version", help="the version, without the leading v")
    parser.add_argument("--output", "-o", type=Path, help="write here instead of to stdout")
    parser.add_argument(
        "--dry-run", action="store_true", help="take [Unreleased] if the version has no section"
    )
    args = parser.parse_args(argv)
    try:
        changelog = CHANGELOG.read_text(encoding="utf-8")
        notes = release_notes(changelog, args.version, dry_run=args.dry_run)
    except NotesError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    if args.output is None:
        sys.stdout.write(notes)
    else:
        atomic_write_bytes(args.output, notes.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
