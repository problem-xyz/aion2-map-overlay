"""scripts/bump_version.py and scripts/check_version.py, the two halves of tag == version.

Both are command-line scripts rather than modules of the app, so they are loaded by path, as
test_version_info.py loads packaging/version_info.py. Every git command runs in a throwaway
repository under tmp_path with the global and system git config replaced: a real bump can never
touch this checkout, and the identity guard meets a global identity the test controls.
"""

import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

import map_overlay
from map_overlay.core.appinfo import APP_NAME, PACK_ID, PUBLISHER
from map_overlay.store.routes import SHIPPED_DIGESTS, route_digest

REPO = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK_VERSION = REPO / "scripts" / "check_version.py"
bump = load_script(REPO / "scripts" / "bump_version.py", "bump_version")
check_version = load_script(CHECK_VERSION, "check_version")
version_info = load_script(REPO / "packaging" / "version_info.py", "packaging_version_info")

CURRENT = "1.0.0-beta.0"
NEW = "1.0.0-beta.1"
DAY = date(2026, 9, 22)
REPO_IDENTITY = ("Release Handle", "handle@users.noreply.example.com")
GLOBAL_IDENTITY = ("Real Name", "real.name@example.com")
RELEASE_FILES = {bump.INIT_FILE, bump.PACKAGE_JSON, bump.PACKAGE_LOCK, bump.CHANGELOG}

# Each is forbidden by SemVer 2.0.0 and was accepted by the looser rule this replaced.
SEMVER_FORBIDS = [
    "1.0.0-beta..1",
    "1.0.0-beta.",
    "1.0.0-.beta",
    "01.0.0",
    "1.00.0",
    "1.0.0-beta.01",
    "\uff11.0.0",
    "\u0661.\u0660.\u0660",
    "1\u0660.0.0",
    "1.0.0-a\u0661",
]

# The real CHANGELOG's [Unreleased] is empty straight after every release, so it cannot serve
# as the fixture; this one has its shape.
CHANGELOG_TEXT = """\
# Changelog

Intro.

## [Unreleased]

### Added

- A new thing.

### Fixed

- An old thing.

## [1.0.0-beta.0] - 2026-08-01

### Added

- The first thing.
"""


def run_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.strip()


@pytest.fixture
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git sees each repository's own config, plus a global one naming somebody else."""
    config = tmp_path / "global.gitconfig"
    name, email = GLOBAL_IDENTITY
    config.write_bytes(f"[user]\n\tname = {name}\n\temail = {email}\n".encode())
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for variable in (*bump.IDENTITY_ENV, "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        monkeypatch.delenv(variable, raising=False)


def make_repo(root: Path, identity: tuple[str | None, str | None]) -> Path:
    """A repository holding copies of the release files, at version CURRENT."""
    for path in (bump.PACKAGE_JSON, bump.PACKAGE_LOCK, bump.INIT_FILE):
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_bytes((REPO / path).read_bytes())
    init = root / bump.INIT_FILE
    pinned = bump.INIT_VERSION.sub(f'__version__ = "{CURRENT}"', init.read_bytes().decode())
    init.write_bytes(pinned.encode())
    (root / bump.CHANGELOG).write_bytes(CHANGELOG_TEXT.encode())

    run_git(root, "init", "--quiet", "--initial-branch=main")
    for key, value in zip(("user.name", "user.email"), identity, strict=True):
        if value is not None:
            run_git(root, "config", "--local", key, value)
    run_git(root, "add", "--all")
    run_git(root, "commit", "--quiet", "-m", "initial")
    return root


@pytest.fixture
def repo(tmp_path: Path, isolated_git: None) -> Path:
    return make_repo(tmp_path / "repo", REPO_IDENTITY)


def add_entry(root: Path, entry: str) -> None:
    """Give [Unreleased] something to release, committed so that a real run starts clean."""
    path = root / bump.CHANGELOG
    text = path.read_bytes().decode()
    added = f"## [Unreleased]\n\n### Fixed\n\n- {entry}\n"
    path.write_bytes(text.replace("## [Unreleased]\n", added, 1).encode())
    run_git(root, "commit", "--quiet", "--all", "-m", entry)


def snapshot(root: Path) -> tuple[str, str, dict[str, bytes]]:
    """Status, every ref, and the bytes of every file outside .git."""
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }
    refs = run_git(root, "for-each-ref", "--format=%(refname) %(objectname)")
    return run_git(root, "status", "--porcelain"), refs, files


def accepts(parse: Callable[[str], object], error: type[Exception], candidate: str) -> bool:
    try:
        parse(candidate)
    except error:
        return False
    return True


@pytest.mark.parametrize(
    "candidate",
    [
        "1.0.0",
        "1.0.0-beta.1",
        "2.10.3-rc.1",
        "0.1.0-alpha",
        "",
        "1",
        "1.0",
        "1.0.0.0",
        "v1.0.0",
        "1.0.0-",
        "one.0.0",
        "1.0.0 beta",
        "1.0.0+win",
        "1.0.0-beta_1",
        "1.70000.0",
        *SEMVER_FORBIDS,
        "1.0.0-0",
        "1.0.0-0a.01a",
        "1.0.0--1",
        "1.0.0-beta.1.lock",
    ],
)
def test_a_version_is_valid_exactly_when_the_build_can_stamp_it(candidate: str) -> None:
    """bump_version.py and packaging/version_info.py cannot disagree about what a version is."""
    stamped = accepts(version_info.file_version, ValueError, candidate)
    assert accepts(bump.parse_version, bump.RefusedError, candidate) == stamped


@pytest.mark.parametrize("candidate", [" 1.0.0", "1.0.0 ", "1.0.0\n"])
def test_whitespace_the_build_forgives_is_still_refused(candidate: str) -> None:
    """file_version() strips its input; a tag named `v1.0.0 ` would be a different tag."""
    assert version_info.file_version(candidate) == (1, 0, 0, 0)
    with pytest.raises(bump.RefusedError):
        bump.parse_version(candidate)


# Lowest first: SemVer 2.0.0 section 11's own example, plus the cases a string sort gets wrong.
ORDERED = [
    "0.9.0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.0",
    "1.0.0-beta.2",
    "1.0.0-beta.10",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
    "1.0.1",
    "1.1.0",
    "1.10.0",
    "2.0.0-alpha",
    "2.0.0",
]


def test_versions_are_ordered_by_semver_precedence() -> None:
    """beta.10 follows beta.9, a release follows its prereleases, alpha.1 precedes alpha.beta."""
    keys = [bump.parse_version(version) for version in ORDERED]
    assert all(lower < higher for lower, higher in itertools.pairwise(keys))


@pytest.mark.parametrize("dry_run", [False, True], ids=["release", "dry run"])
@pytest.mark.parametrize("version", ["1.0.0-beta.1", "1.0.0-alpha.9", "0.9.9"])
def test_a_bump_must_move_past_the_highest_release_tag(
    repo: Path, capsys: pytest.CaptureFixture[str], version: str, dry_run: bool
) -> None:
    """1.0.0-beta.1 is above __version__ here, but below the tag: the tag is what shipped."""
    run_git(repo, "tag", "v1.0.0-beta.2")
    before = snapshot(repo)
    assert bump.main([version, *(["--dry-run"] if dry_run else [])], root=repo, today=DAY) == 1
    err = capsys.readouterr().err
    assert f"{version} is not greater than v1.0.0-beta.2, the highest release tag" in err
    assert snapshot(repo) == before


def test_the_first_release_may_sort_below_the_placeholder_version(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A first release of 1.0.0-alpha.1, while __version__ holds the 1.0.0-beta.0 placeholder."""
    assert bump.parse_version("1.0.0-alpha.1") < bump.parse_version(CURRENT)
    before = snapshot(repo)
    assert bump.main(["1.0.0-alpha.1", "--dry-run"], root=repo, today=DAY) == 0
    out = capsys.readouterr().out
    assert f"dry run: {CURRENT} -> 1.0.0-alpha.1, nothing is written" in out
    assert "after:  no release tag here, so there is no earlier release to compare with" in out
    assert snapshot(repo) == before


def test_each_release_is_ordered_against_the_tags_of_the_ones_before(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """alpha.1 then alpha.2, and beta.1 after them, in one throwaway repository."""
    assert bump.latest_release(repo) is None
    assert bump.main(["1.0.0-alpha.1"], root=repo, today=DAY) == 0
    assert run_git(repo, "tag", "--list") == "v1.0.0-alpha.1"
    capsys.readouterr()

    add_entry(repo, "Second.")
    before = snapshot(repo)
    assert bump.main(["1.0.0-alpha.1", "--dry-run"], root=repo, today=DAY) == 1
    assert "already has a section for 1.0.0-alpha.1" in capsys.readouterr().err
    assert bump.main(["1.0.0-alpha.0", "--dry-run"], root=repo, today=DAY) == 1
    err = capsys.readouterr().err
    assert "1.0.0-alpha.0 is not greater than v1.0.0-alpha.1, the highest release tag" in err
    assert bump.main(["1.0.0-alpha.2", "--dry-run"], root=repo, today=DAY) == 0
    out = capsys.readouterr().out
    assert "dry run: 1.0.0-alpha.1 -> 1.0.0-alpha.2" in out
    assert "after:  v1.0.0-alpha.1, the highest release tag here\n" in out
    assert snapshot(repo) == before
    assert bump.main(["1.0.0-alpha.2"], root=repo, today=DAY) == 0

    add_entry(repo, "Third.")
    before = snapshot(repo)
    assert bump.main(["1.0.0-alpha.1"], root=repo, today=DAY) == 1
    assert "already has a section for 1.0.0-alpha.1" in capsys.readouterr().err
    assert bump.main(["1.0.0-alpha.1.1"], root=repo, today=DAY) == 1
    err = capsys.readouterr().err
    assert "1.0.0-alpha.1.1 is not greater than v1.0.0-alpha.2, the highest release tag" in err
    assert snapshot(repo) == before
    assert bump.main(["1.0.0-beta.1"], root=repo, today=DAY) == 0

    tags = run_git(repo, "tag", "--list").split("\n")
    assert sorted(tags) == ["v1.0.0-alpha.1", "v1.0.0-alpha.2", "v1.0.0-beta.1"]
    assert bump.latest_release(repo) == "1.0.0-beta.1"
    init = (repo / bump.INIT_FILE).read_bytes().decode()
    assert '__version__ = "1.0.0-beta.1"' in init


def test_the_highest_tag_is_found_by_semver_and_other_tags_are_passed_over(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """beta.10 outranks beta.9, which a string sort gets wrong; v01.0.0 is not a version."""
    for tag in ("v1.0.0-beta.9", "v1.0.0-beta.10", "vnext", "v9.9.9+build", "v01.0.0", "v2.0"):
        run_git(repo, "tag", tag)
    assert bump.latest_release(repo) == "1.0.0-beta.10"
    before = snapshot(repo)
    assert bump.main(["1.0.0-beta.9.1", "--dry-run"], root=repo, today=DAY) == 1
    err = capsys.readouterr().err
    assert "1.0.0-beta.9.1 is not greater than v1.0.0-beta.10, the highest release tag" in err
    assert bump.main(["1.0.0-beta.11", "--dry-run"], root=repo, today=DAY) == 0
    assert "after:  v1.0.0-beta.10, the highest release tag here\n" in capsys.readouterr().out
    assert snapshot(repo) == before


def test_tags_that_are_not_versions_leave_the_first_release_open(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for tag in ("vnext", "v9.9.9+build", "v01.0.0", "9.9.9"):
        run_git(repo, "tag", tag)
    assert bump.latest_release(repo) is None
    assert bump.main(["1.0.0-alpha.1", "--dry-run"], root=repo, today=DAY) == 0
    assert "after:  no release tag here" in capsys.readouterr().out


@pytest.mark.parametrize("dry_run", [False, True], ids=["release", "dry run"])
def test_a_version_git_cannot_tag_is_refused_before_anything_is_written(
    repo: Path, capsys: pytest.CaptureFixture[str], dry_run: bool
) -> None:
    """Valid SemVer, invalid ref: found only at `git tag`, it would leave a commit without a tag."""
    version = "1.0.0-beta.1.lock"
    bump.parse_version(version)
    before = snapshot(repo)
    assert bump.main([version, *(["--dry-run"] if dry_run else [])], root=repo, today=DAY) == 1
    assert f"git does not accept v{version} as a tag name" in capsys.readouterr().err
    assert snapshot(repo) == before


@pytest.mark.parametrize("dry_run", [False, True], ids=["release", "dry run"])
def test_a_tag_git_cannot_create_is_refused_before_anything_is_written(
    repo: Path, capsys: pytest.CaptureFixture[str], dry_run: bool
) -> None:
    """A well-formed name that does not exist yet can still fail at `git tag`.

    A ref underneath v<version> makes that name a directory: check-ref-format passes and the tag
    is absent, so only rehearsing the creation finds it. Deterministic on every platform, unlike
    the other way to get there, a lock path past Windows' 260-character limit.
    """
    run_git(repo, "update-ref", f"refs/tags/v{NEW}/blocker", "HEAD")
    before = snapshot(repo)
    assert bump.main([NEW, *(["--dry-run"] if dry_run else [])], root=repo, today=DAY) == 1
    assert f"git could not create tag v{NEW} here" in capsys.readouterr().err
    assert snapshot(repo) == before


def test_a_numeric_identifier_too_long_for_int_still_orders_correctly() -> None:
    """SemVer sets no length limit; Python refuses int() on a string over 4300 digits."""
    nines = "1.0.0-" + "9" * 4400
    ten_to_the_4400 = "1.0.0-1" + "0" * 4400
    ten_to_the_4399 = "1.0.0-1" + "0" * 4399
    assert bump.parse_version(nines) < bump.parse_version(ten_to_the_4400)
    assert bump.parse_version(ten_to_the_4399) < bump.parse_version(nines)
    # Numeric identifiers still sort below alphanumeric ones, however long.
    assert bump.parse_version(nines) < bump.parse_version("1.0.0-a")


@pytest.mark.parametrize(
    "version", ["1.0", "1.0.0+build", "v1.0.0-beta.1", "v1.0.0-beta..1", *SEMVER_FORBIDS]
)
def test_an_invalid_version_is_refused(
    repo: Path, capsys: pytest.CaptureFixture[str], version: str
) -> None:
    before = snapshot(repo)
    assert bump.main([version, "--dry-run"], root=repo, today=DAY) == 1
    err = capsys.readouterr().err
    assert f"cannot parse version {version!r}" in err
    assert ("leave off the v" in err) == version.startswith("v")
    assert snapshot(repo) == before


def test_the_unreleased_entries_move_under_a_dated_heading() -> None:
    """[Unreleased] stays, empty, above the new section; everything else is untouched."""
    assert bump.release_changelog(CHANGELOG_TEXT, NEW, DAY) == CHANGELOG_TEXT.replace(
        "## [Unreleased]\n", f"## [Unreleased]\n\n## [{NEW}] - 2026-09-22\n"
    )


def test_the_compare_links_move_on_by_one_release() -> None:
    links = (
        "\n"
        "[unreleased]: https://github.com/o/r/compare/v1.0.0-beta.0...HEAD\n"
        "[1.0.0-beta.0]: https://github.com/o/r/releases/tag/v1.0.0-beta.0\n"
    )
    released = bump.release_changelog(CHANGELOG_TEXT + links, NEW, DAY)
    assert released.endswith(
        "\n"
        f"[unreleased]: https://github.com/o/r/compare/v{NEW}...HEAD\n"
        f"[{NEW}]: https://github.com/o/r/compare/v1.0.0-beta.0...v{NEW}\n"
        "[1.0.0-beta.0]: https://github.com/o/r/releases/tag/v1.0.0-beta.0\n"
    )
    assert f"## [Unreleased]\n\n## [{NEW}] - 2026-09-22\n\n### Added\n" in released


def test_a_first_release_ends_at_the_links_and_keeps_their_label() -> None:
    """With no older section, the entries run up to the link block, not past it."""
    text = (
        "# Changelog\n\n## [Unreleased]\n\n- First.\n\n"
        "[Unreleased]: https://github.com/o/r/compare/abc1234...HEAD\n"
    )
    assert bump.release_changelog(text, "1.0.0", DAY) == (
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-09-22\n\n- First.\n\n"
        "[Unreleased]: https://github.com/o/r/compare/v1.0.0...HEAD\n"
        "[1.0.0]: https://github.com/o/r/compare/abc1234...v1.0.0\n"
    )


def test_an_unreleased_link_of_another_shape_is_refused_rather_than_left_stale() -> None:
    text = CHANGELOG_TEXT + "\n[unreleased]: https://github.com/o/r/commits/main\n"
    with pytest.raises(bump.RefusedError, match=re.escape("compare/<tag>...HEAD")):
        bump.release_changelog(text, NEW, DAY)


@pytest.mark.parametrize(
    "text",
    [
        "# Changelog\n\n## [Unreleased]\n\n## [1.0.0] - 2026-01-01\n\n- Old.\n",
        "# Changelog\n\n## [Unreleased]\n\n### Added\n\n### Fixed\n\n## [1.0.0] - 2026-01-01\n",
        "# Changelog\n\n## [Unreleased]\n",
        "# Changelog\n\n## [Unreleased]\n\n[unreleased]: https://x/compare/v1.0.0...HEAD\n",
    ],
    ids=["no entries", "headings only", "end of file", "links only"],
)
def test_an_empty_unreleased_is_refused(text: str) -> None:
    """A release with nothing in it has nothing to say in its notes."""
    with pytest.raises(bump.RefusedError, match="empty"):
        bump.release_changelog(text, NEW, DAY)


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("# Changelog\n\n## [1.0.0] - 2026-01-01\n\n- Old.\n", "exactly one"),
        (CHANGELOG_TEXT + f"\n## [{NEW}] - 2026-09-01\n\n- Early.\n", "already has a section"),
    ],
    ids=["no unreleased", "section exists"],
)
def test_a_changelog_that_cannot_take_the_release_is_refused(text: str, reason: str) -> None:
    with pytest.raises(bump.RefusedError, match=reason):
        bump.release_changelog(text, NEW, DAY)


@pytest.mark.parametrize(
    "heading",
    [
        "### Added",
        "### added",
        "### Added  ",
        # Each of these renders as the same "Added" heading in CommonMark.
        "###  Added",
        "###\tAdded",
        " ### Added",
        "   ### Added",
        "### Added ###",
        "### Added #",
    ],
)
def test_a_repeated_subsection_in_unreleased_is_refused(heading: str) -> None:
    """Two `### Added` lists would reach the release notes as two; the older sections may repeat."""
    text = CHANGELOG_TEXT.replace("### Fixed\n", f"{heading}\n\n- Another.\n\n### Fixed\n")
    with pytest.raises(bump.RefusedError, match=r"more than one '### [Aa]dded' subsection"):
        bump.release_changelog(text, NEW, DAY)


def test_a_heading_indented_four_spaces_is_code_not_a_second_subsection() -> None:
    """Four spaces of indent after a heading is a code block in CommonMark, not a heading.

    It sits directly under a heading on purpose: after a list item the same line would continue
    the item, and CommonMark could render it as a heading nested inside it.
    """
    text = CHANGELOG_TEXT.replace("### Fixed\n", "### Fixed\n\n    ### Added\n")
    assert f"## [{NEW}] - {DAY.isoformat()}" in bump.release_changelog(text, NEW, DAY)


def test_a_repeated_subsection_stops_the_whole_release(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = CHANGELOG_TEXT.replace("## [1.0.0-beta.0]", "### Added\n\n- Later.\n\n## [1.0.0-beta.0]")
    (repo / bump.CHANGELOG).write_bytes(text.encode())
    run_git(repo, "commit", "--quiet", "--all", "-m", "second added")
    before = snapshot(repo)
    for dry_run in ([], ["--dry-run"]):
        assert bump.main([NEW, *dry_run], root=repo, today=DAY) == 1
        assert "has more than one '### Added' subsection" in capsys.readouterr().err
    assert snapshot(repo) == before


def test_the_changelog_in_this_repository_can_be_released() -> None:
    """A repeated subsection fails here, in the pull request that adds it, not at release time."""
    text = (REPO / bump.CHANGELOG).read_bytes().decode()
    try:
        bump.release_changelog(text, "99.0.0", DAY)
    except bump.RefusedError as refusal:
        # Straight after a release [Unreleased] is empty, which is the one expected refusal.
        assert "is empty" in str(refusal)


def test_an_empty_unreleased_stops_the_whole_release(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = "# Changelog\n\n## [Unreleased]\n\n## [1.0.0-beta.0] - 2026-08-01\n\n- First.\n"
    (repo / bump.CHANGELOG).write_bytes(text.encode())
    run_git(repo, "commit", "--quiet", "--all", "-m", "empty unreleased")
    before = snapshot(repo)
    assert bump.main([NEW], root=repo, today=DAY) == 1
    assert "is empty" in capsys.readouterr().err
    assert snapshot(repo) == before


def test_the_npm_files_change_in_their_root_version_lines_only(repo: Path) -> None:
    _, changes = bump.plan_release(repo, NEW, DAY)
    by_path = {change.path: change for change in changes}
    for path, expected in ((bump.PACKAGE_JSON, 1), (bump.PACKAGE_LOCK, 2)):
        before = by_path[path].before.split("\n")
        after = by_path[path].after.split("\n")
        assert len(after) == len(before)
        changed = [new for old, new in zip(before, after, strict=True) if old != new]
        assert len(changed) == expected, path
        assert all(f'"version": "{NEW}"' in line for line in changed)

    lock_before = json.loads(by_path[bump.PACKAGE_LOCK].before)
    lock_after = json.loads(by_path[bump.PACKAGE_LOCK].after)
    assert lock_after["version"] == lock_after["packages"][""]["version"] == NEW
    del lock_before["packages"][""]["version"], lock_after["packages"][""]["version"]
    del lock_before["version"], lock_after["version"]
    assert lock_after == lock_before


def test_a_version_key_elsewhere_in_the_file_is_never_the_one_rewritten() -> None:
    """The in-place edit is checked by parsing, so an unexpected layout refuses instead."""
    text = '{\n  "dependencies": {"x": {"version": "2.0.0"}},\n  "version": "2.0.0"\n}\n'
    with pytest.raises(bump.RefusedError, match="not laid out"):
        bump.set_json_versions(text, [("version",)], NEW, "package.json")


def test_a_dry_run_prints_every_diff_and_changes_nothing(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = snapshot(repo)
    assert bump.main([NEW, "--dry-run"], root=repo, today=DAY) == 0
    assert snapshot(repo) == before

    out = capsys.readouterr().out
    for path in RELEASE_FILES:
        assert f"--- a/{path}\n+++ b/{path}\n" in out
    assert f'+__version__ = "{NEW}"' in out
    assert f'+  "version": "{NEW}",' in out
    assert f'+      "version": "{NEW}",' in out
    assert f"+## [{NEW}] - 2026-09-22" in out
    assert f"commit: chore(release): {NEW}\n" in out
    assert f"tag:    v{NEW} (annotated" in out
    assert "after:  no release tag here" in out
    assert f"as:     {REPO_IDENTITY[0]} <{REPO_IDENTITY[1]}>" in out
    assert "note:" not in out


@pytest.mark.parametrize("dirt", ["modified", "untracked"])
def test_a_dirty_tree_stops_a_release_but_not_a_dry_run(
    repo: Path, capsys: pytest.CaptureFixture[str], dirt: str
) -> None:
    """An untracked file counts: it may be the one the release was tested with."""
    if dirt == "modified":
        (repo / bump.CHANGELOG).write_bytes(CHANGELOG_TEXT.encode() + b"\nUncommitted.\n")
    else:
        (repo / "stray.py").write_bytes(b"")
    before = snapshot(repo)

    assert bump.main([NEW], root=repo, today=DAY) == 1
    assert "working tree is not clean" in capsys.readouterr().err
    assert snapshot(repo) == before

    assert bump.main([NEW, "--dry-run"], root=repo, today=DAY) == 0
    assert "note:   the working tree is not clean" in capsys.readouterr().out
    assert snapshot(repo) == before


@pytest.mark.parametrize("dry_run", [False, True], ids=["release", "dry run"])
def test_an_existing_tag_is_refused(
    repo: Path, capsys: pytest.CaptureFixture[str], dry_run: bool
) -> None:
    run_git(repo, "tag", f"v{NEW}")
    before = snapshot(repo)
    assert bump.main([NEW, *(["--dry-run"] if dry_run else [])], root=repo, today=DAY) == 1
    assert f"tag v{NEW} already exists" in capsys.readouterr().err
    assert snapshot(repo) == before


@pytest.mark.parametrize("dry_run", [False, True], ids=["release", "dry run"])
@pytest.mark.parametrize(
    "identity",
    [(None, None), (REPO_IDENTITY[0], None), (None, REPO_IDENTITY[1])],
    ids=["neither", "name only", "email only"],
)
def test_without_a_repository_identity_nothing_is_released(
    tmp_path: Path,
    isolated_git: None,
    capsys: pytest.CaptureFixture[str],
    identity: tuple[str | None, str | None],
    dry_run: bool,
) -> None:
    """The global identity git would fall back to is the owner's real name; it never signs."""
    repo = make_repo(tmp_path / "repo", identity)
    before = snapshot(repo)
    assert bump.main([NEW, *(["--dry-run"] if dry_run else [])], root=repo, today=DAY) == 1
    assert "no repository-level git identity" in capsys.readouterr().err
    assert snapshot(repo) == before


def test_a_release_is_committed_and_tagged_as_the_repository_identity(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    parent = run_git(repo, "rev-parse", "HEAD")
    # Git would record these over user.name and user.email; the script must not let it.
    global_name, global_email = GLOBAL_IDENTITY
    for variable in bump.IDENTITY_ENV:
        monkeypatch.setenv(variable, global_email if variable.endswith("EMAIL") else global_name)

    assert bump.main([NEW], root=repo, today=DAY) == 0

    name, email = REPO_IDENTITY
    head = run_git(repo, "rev-parse", "HEAD")
    assert run_git(repo, "log", "-1", "--format=%an|%ae|%cn|%ce|%P|%s") == (
        f"{name}|{email}|{name}|{email}|{parent}|chore(release): {NEW}"
    )
    assert set(run_git(repo, "show", "--name-only", "--format=", "HEAD").split("\n")) == (
        RELEASE_FILES
    )
    assert run_git(repo, "cat-file", "-t", f"v{NEW}") == "tag"
    tag = "%(taggername)|%(taggeremail)|%(*objectname)|%(contents:subject)"
    assert run_git(repo, "for-each-ref", f"--format={tag}", f"refs/tags/v{NEW}") == (
        f"{name}|<{email}>|{head}|{APP_NAME} {NEW}"
    )
    assert run_git(repo, "status", "--porcelain") == ""

    assert f'__version__ = "{NEW}"' in (repo / bump.INIT_FILE).read_text(encoding="utf-8")
    package = json.loads((repo / bump.PACKAGE_JSON).read_bytes())
    assert package["version"] == NEW
    changelog = (repo / bump.CHANGELOG).read_text(encoding="utf-8")
    assert f"## [Unreleased]\n\n## [{NEW}] - 2026-09-22\n\n### Added\n\n- A new thing." in changelog
    assert f"git push --atomic origin main v{NEW}" in capsys.readouterr().out


STARTER = REPO / "assets" / "routes" / "Asmodians_-_Level_10-17.json"
DIGESTS = f"{bump.STARTER_ROUTES}/{SHIPPED_DIGESTS}"


def add_starter_route(root: Path, digests: str | None) -> str:
    """Commit a starter route, and a digests file if given; the line a release adds for it."""
    (root / bump.STARTER_ROUTES).mkdir(parents=True)
    (root / bump.STARTER_ROUTES / STARTER.name).write_bytes(STARTER.read_bytes())
    if digests is not None:
        (root / DIGESTS).write_bytes(digests.encode())
    run_git(root, "add", "--all")
    run_git(root, "commit", "--quiet", "-m", "starter route")
    return f"{route_digest(STARTER.read_bytes())}  {STARTER.name}"


def test_a_release_records_the_starter_routes_it_ships(repo: Path) -> None:
    line = add_starter_route(repo, "# header\n")

    assert bump.main([NEW], root=repo, today=DAY) == 0

    assert (repo / DIGESTS).read_text(encoding="utf-8") == f"# header\n{line}\n"
    assert DIGESTS in run_git(repo, "show", "--name-only", "--format=", "HEAD").split("\n")


def test_a_starter_route_already_recorded_changes_nothing(repo: Path) -> None:
    line = add_starter_route(repo, None)
    (repo / DIGESTS).write_bytes(f"{line}\n".encode())
    run_git(repo, "add", "--all")
    run_git(repo, "commit", "--quiet", "-m", "digests")

    _, changes = bump.plan_release(repo, NEW, DAY)

    assert {change.path for change in changes} == RELEASE_FILES


def test_the_identity_the_guard_checked_is_the_one_recorded(repo: Path) -> None:
    """An include later in .git/config outranks [user] for git, but not for the guard's read."""
    included = repo.parent / "included.gitconfig"
    included.write_bytes(
        f"[user]\n\tname = {GLOBAL_IDENTITY[0]}\n\temail = {GLOBAL_IDENTITY[1]}\n".encode()
    )
    run_git(repo, "config", "--local", "include.path", str(included))
    assert run_git(repo, "config", "user.name") == GLOBAL_IDENTITY[0]

    assert bump.main([NEW], root=repo, today=DAY) == 0

    name, email = REPO_IDENTITY
    assert (
        run_git(repo, "log", "-1", "--format=%an|%ae|%cn|%ce") == f"{name}|{email}|{name}|{email}"
    )
    tagger = run_git(repo, "for-each-ref", "--format=%(taggername)|%(taggeremail)", "refs/tags")
    assert tagger == f"{name}|<{email}>"


@pytest.mark.parametrize(
    ("ref_name", "version", "status"),
    [
        ("v1.0.0-beta.1", "1.0.0-beta.1", 0),
        ("v1.0.0", "1.0.0", 0),
        ("v1.0.0-beta.2", "1.0.0-beta.1", check_version.MISMATCH),
        ("v1.0.0", "1.0.0-beta.1", check_version.MISMATCH),
        ("v1.0.0-beta.1", "1.0.0-beta.10", check_version.MISMATCH),
        (None, "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("", "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("main", "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("44/merge", "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("1.0.0", "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("v1.0", "1.0.0", check_version.NOTHING_TO_COMPARE),
        ("vnext", "1.0.0", check_version.NOTHING_TO_COMPARE),
    ],
)
def test_a_ref_is_compared_only_when_it_is_a_version_tag(
    ref_name: str | None, version: str, status: int
) -> None:
    assert check_version.check(ref_name, version)[0] == status


def test_the_tag_of_the_code_version_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_REF_NAME", f"v{map_overlay.__version__}")
    assert check_version.main([]) == 0
    assert "matches" in capsys.readouterr().out


def test_the_check_runs_without_pyinstaller() -> None:
    """The version rule lives beside the build, but PyInstaller is a dev-group dependency."""
    # None in sys.modules makes every import of the package fail, as if it were not installed.
    code = (
        "import runpy, sys\n"
        "sys.modules['PyInstaller'] = None\n"
        f"runpy.run_path({str(CHECK_VERSION)!r}, run_name='__main__')\n"
    )
    env = {**os.environ, "GITHUB_REF_NAME": f"v{map_overlay.__version__}"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "matches" in result.stdout


def test_a_tag_of_another_version_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("GITHUB_REF_NAME", "v99.0.0")
    assert check_version.main([]) == 1
    expected = f"tag v99.0.0 does not match __version__ {map_overlay.__version__}"
    assert expected in capsys.readouterr().err


@pytest.mark.parametrize("value", [None, ""], ids=["unset", "empty"])
def test_a_missing_ref_name_is_not_reported_as_a_mismatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], value: str | None
) -> None:
    if value is None:
        monkeypatch.delenv("GITHUB_REF_NAME", raising=False)
    else:
        monkeypatch.setenv("GITHUB_REF_NAME", value)
    assert check_version.main([]) == check_version.NOTHING_TO_COMPARE
    assert "GITHUB_REF_NAME is not set" in capsys.readouterr().err


@pytest.mark.parametrize("ref_name", ["main", "44/merge", "latest"])
def test_a_branch_build_is_not_reported_as_a_mismatch(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], ref_name: str
) -> None:
    """What ci.yml would see: the reason this script is not wired into it."""
    monkeypatch.setenv("GITHUB_REF_NAME", ref_name)
    assert check_version.main([]) == check_version.NOTHING_TO_COMPARE
    assert f"{ref_name!r} is not a version tag" in capsys.readouterr().err


def test_a_ref_given_as_an_argument_is_compared_instead_of_the_environment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A manual run of release.yml is on a branch and names the tag it builds as the argument."""
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    assert check_version.main([f"v{map_overlay.__version__}"]) == 0
    assert "matches" in capsys.readouterr().out
    assert check_version.main(["v99.0.0"]) == 1
    assert "tag v99.0.0 does not match" in capsys.readouterr().err


def test_the_release_takes_its_names_from_appinfo_and_is_never_a_pre_release() -> None:
    # Renaming the app is an edit to core/appinfo.py alone, and latest/download/ skips pre-releases.
    for rel in (".github/workflows/release.yml", "scripts/pack.ps1"):
        text = (REPO / rel).read_text(encoding="utf-8")
        for name in (APP_NAME, PACK_ID, PUBLISHER):
            assert name not in text, f"{rel} spells out {name!r}"
    workflow = (REPO / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "vpk upload github" in workflow
    assert not re.search(r"--pre\b", workflow)
