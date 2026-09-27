"""scripts/release_notes.py, which turns a CHANGELOG section into the notes of a GitHub release.

The script is a command-line tool rather than a module of the app, so it is loaded by path, as
test_release_scripts.py loads its scripts.
"""

import importlib.util
import re
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from map_overlay.core.appinfo import APP_NAME, PACK_ID

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


notes = load_script(REPO / "scripts" / "release_notes.py", "release_notes")
bump = load_script(REPO / "scripts" / "bump_version.py", "bump_version")

CHANGELOG = """\
# Changelog

Intro.

## [Unreleased]

### Added

- Not released yet.

## [1.0.0-beta.2] - 2026-10-02

### Fixed

- The second release.

## [1.0.0-beta.1] - 2026-10-01

### Added

- The first release.

### Fixed

- Something from before.

[unreleased]: https://example.invalid/compare/v1.0.0-beta.2...HEAD
[1.0.0-beta.2]: https://example.invalid/compare/v1.0.0-beta.1...v1.0.0-beta.2
"""


def test_the_notes_are_that_release_s_section_without_its_heading() -> None:
    assert (
        notes.changelog_section(CHANGELOG, "1.0.0-beta.2") == "### Fixed\n\n- The second release."
    )


def test_the_last_section_stops_before_the_link_definitions() -> None:
    section = notes.changelog_section(CHANGELOG, "1.0.0-beta.1")
    assert section == "### Added\n\n- The first release.\n\n### Fixed\n\n- Something from before."


def test_a_version_is_matched_whole_and_not_as_a_prefix() -> None:
    with pytest.raises(notes.NotesError, match=re.escape("no section for 1.0.0-beta:")):
        notes.changelog_section(CHANGELOG, "1.0.0-beta")


def test_a_release_without_a_section_is_refused() -> None:
    with pytest.raises(notes.NotesError, match=re.escape("no section for 1.0.0-beta.3")):
        notes.release_notes(CHANGELOG, "1.0.0-beta.3")


def test_a_dry_run_of_a_version_not_cut_yet_takes_the_unreleased_section() -> None:
    text = notes.release_notes(CHANGELOG, "1.0.0-beta.3", dry_run=True)
    assert text.startswith("### Added\n\n- Not released yet.\n\n## How to install\n")
    released = notes.release_notes(CHANGELOG, "1.0.0-beta.2", dry_run=True)
    assert released == notes.release_notes(CHANGELOG, "1.0.0-beta.2")


def test_an_empty_section_is_refused() -> None:
    changelog = CHANGELOG.replace("### Fixed\n\n- The second release.\n", "### Fixed\n")
    with pytest.raises(notes.NotesError, match="empty"):
        notes.changelog_section(changelog, "1.0.0-beta.2")


def test_the_notes_end_with_how_to_install_under_the_app_s_own_names() -> None:
    text = notes.release_notes(CHANGELOG, "1.0.0-beta.2")
    assert text.startswith("### Fixed\n\n- The second release.\n\n## How to install\n")
    for name in (f"{PACK_ID}-win-Setup.exe", f"{PACK_ID}-win-Portable.zip", f"{APP_NAME}.exe"):
        assert name in text
    assert "More info" in text
    # Setup.exe is downloaded on its own; the notes say where Velopack's licences are.
    assert "THIRD-PARTY-NOTICES\\velopack" in text


def test_the_section_bump_version_writes_is_the_one_the_notes_take() -> None:
    real = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    released = bump.release_changelog(real, "9.9.9", date(2026, 9, 23))
    section = notes.changelog_section(released, "9.9.9")
    unreleased = real.split("## [Unreleased]", 1)[1]
    assert section.split("\n", 1)[0] == unreleased.strip().split("\n", 1)[0]
    assert section.strip() in unreleased


def test_the_command_writes_the_file_or_refuses_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setattr(notes, "CHANGELOG", changelog)
    out = tmp_path / "notes.md"

    assert notes.main(["1.0.0-beta.1", "--output", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == notes.release_notes(CHANGELOG, "1.0.0-beta.1")

    missing = tmp_path / "missing.md"
    assert notes.main(["2.0.0", "--output", str(missing)]) == 1
    assert not missing.exists()
    assert "refused: CHANGELOG.md has no section for 2.0.0" in capsys.readouterr().err
