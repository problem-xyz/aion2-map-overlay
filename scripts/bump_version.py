"""Cut a release: bump the version everywhere, date the CHANGELOG section, commit and tag.

    uv run python scripts/bump_version.py 1.0.0-beta.1 --dry-run   # show what would change
    uv run python scripts/bump_version.py 1.0.0-beta.1             # change, commit, tag

`src/map_overlay/__init__.py` is the one source of the version. `ui/package.json` and the two
root fields of `ui/package-lock.json` hold copies only because npm expects them; nothing reads
them back. `npm ci` does not even compare them (measured on npm 11.17: it accepts a lockfile
whose root version differs from package.json and checks only the dependencies), so the lockfile
is rewritten to keep the next unrelated `npm install` from carrying the change.

`CHANGELOG.md` gets its `[Unreleased]` entries moved under `## [<version>] - <date>`, with an
empty `[Unreleased]` left above them (Keep a Changelog 1.1.0), and its compare links, if it has
any, moved on by one release. Then one commit, `chore(release): <version>`, and an annotated tag
`v<version>`, which is what the release workflow builds from. Nothing is pushed.

What counts as a version is decided by packaging/version_info.py, which has to stamp it into
the exe, so its parser is loaded from there rather than restated here. A version must also be a
tag name git accepts, and greater than the highest `v*` release tag in this clone -- not than
`__version__`, which between releases is a placeholder that says nothing about what has shipped.
The tags are read locally, so fetch them first. Every check runs before anything is written, so a
refusal never leaves half a release behind, and all of them but the clean-tree one run in the dry
run as well.
"""

import argparse
import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from map_overlay.core.appinfo import APP_NAME
from map_overlay.core.fileio import atomic_write_bytes

ROOT = Path(__file__).resolve().parents[1]
VERSION_INFO = ROOT / "packaging" / "version_info.py"

INIT_FILE = "src/map_overlay/__init__.py"
PACKAGE_JSON = "ui/package.json"
PACKAGE_LOCK = "ui/package-lock.json"
CHANGELOG = "CHANGELOG.md"

INIT_VERSION = re.compile(r'^__version__ = "(?P<version>[^"]*)"$', re.MULTILINE)
UNRELEASED_HEADING = re.compile(r"^## \[unreleased\]\s*$", re.IGNORECASE)
SECTION_HEADING = re.compile(r"^## ")
# As CommonMark renders an ATX heading: up to three spaces of indent, any run of spaces or tabs
# after the hashes, and an optional closing sequence. Anything looser lets a second "Added"
# list reach the release notes under a heading that merely looks different in the source.
SUBSECTION_HEADING = re.compile(r"^ {0,3}###[ \t]+(?P<title>.+?)(?:[ \t]+#+)?[ \t]*$")
LINK_DEFINITION = re.compile(r"^\[(?P<label>[^\]]+)\]:\s*(?P<url>\S+)\s*$")
COMPARE_TO_HEAD = re.compile(r"^(?P<base>.+/compare/)(?P<start>.+)\.\.\.HEAD$")

# Each of these beats user.name / user.email in git's own lookup.
IDENTITY_ENV = ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")

type Identifier = tuple[int, int, str]
type VersionKey = tuple[int, int, int, int, tuple[Identifier, ...]]


class RefusedError(Exception):
    """A reason not to release, worded for whoever ran the script."""


class GitError(Exception):
    """A git command failed partway through a real run."""


@dataclass(frozen=True)
class Change:
    path: str
    before: str
    after: str


@dataclass(frozen=True)
class Repository:
    """What the checks found out about the repository a release is cut in."""

    identity: tuple[str, str]
    dirty: bool
    # The highest v* tag that parses as a version, without the v; None before the first release.
    previous: str | None


def _load_version_info() -> ModuleType:
    # packaging/ is a build directory rather than a package, so the file is loaded by path.
    spec = importlib.util.spec_from_file_location("packaging_version_info", VERSION_INFO)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {VERSION_INFO}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


version_info = _load_version_info()


def parse_version(text: str) -> VersionKey:
    """The SemVer 2.0.0 precedence key of `text`, which sorts versions in release order.

    Raises RefusedError for anything packaging/version_info.py would refuse to stamp into the exe.
    """
    try:
        version_info.file_version(text)
    except ValueError as error:
        raise RefusedError(str(error)) from None
    # file_version() forgives surrounding whitespace, which a tag name cannot hold.
    match = version_info.SEMVER.fullmatch(text)
    if match is None:
        raise RefusedError(
            f"cannot parse version {text!r}; expected MAJOR.MINOR.PATCH[-PRERELEASE]"
        )
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    prerelease = match.group(4)
    if prerelease is None:
        return major, minor, patch, 1, ()
    # Numeric identifiers compare as numbers and before alphanumeric ones, which compare in
    # ASCII order; when one list is a prefix of the other the longer one is higher. Tuple
    # comparison does all of that given this shape. A numeric identifier is ordered by its
    # length and then its digits rather than through int(): SemVer forbids leading zeros, so
    # that is the same order, and SemVer sets no length limit while Python refuses int() on a
    # string of more than 4300 digits.
    identifiers = tuple(
        (0, len(part), part) if part.isdigit() else (1, 0, part) for part in prerelease.split(".")
    )
    return major, minor, patch, 0, identifiers


def release_changelog(text: str, version: str, day: date) -> str:
    """`text` with its [Unreleased] entries under a new `## [version] - day` heading."""
    lines = text.split("\n")
    starts = [index for index, line in enumerate(lines) if UNRELEASED_HEADING.match(line)]
    if len(starts) != 1:
        raise RefusedError(
            f"{CHANGELOG} needs exactly one '## [Unreleased]' heading, found {len(starts)}"
        )
    existing = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s|$)")
    if any(existing.match(line) for line in lines):
        raise RefusedError(f"{CHANGELOG} already has a section for {version}")

    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if SECTION_HEADING.match(lines[i])), len(lines)
    )
    # Subsection headings with nothing under them are Keep a Changelog's template, not news.
    if not any(
        line.strip() and not line.startswith("#") and not LINK_DEFINITION.match(line)
        for line in lines[start + 1 : end]
    ):
        raise RefusedError(f"[Unreleased] in {CHANGELOG} is empty, so there is nothing to release")

    _refuse_repeated_headings(lines[start + 1 : end])

    first = next(i for i in range(start + 1, end) if lines[i].strip())
    released = [*lines[: start + 1], "", f"## [{version}] - {day.isoformat()}", "", *lines[first:]]
    return "\n".join(_release_links(released, version))


def _refuse_repeated_headings(section: Iterable[str]) -> None:
    """A second `### Added` would ship as a second list of additions in the release notes."""
    seen: set[str] = set()
    for line in section:
        heading = SUBSECTION_HEADING.match(line)
        if heading is None:
            continue
        title = " ".join(heading["title"].split())
        if title.casefold() in seen:
            raise RefusedError(
                f"[Unreleased] in {CHANGELOG} has more than one '### {title}' subsection: "
                "merge them into one first"
            )
        seen.add(title.casefold())


def _release_links(lines: list[str], version: str) -> list[str]:
    """Move the `[unreleased]` compare link past the new tag and add one for the release.

    Keep a Changelog's shape is `[unreleased]: <repo>/compare/v1.1.0...HEAD` followed by
    `[1.1.0]: <repo>/compare/v1.0.0...v1.1.0`. A file without that link has none to maintain.
    """
    for index, line in enumerate(lines):
        match = LINK_DEFINITION.match(line)
        if match is None or match["label"].lower() != "unreleased":
            continue
        compare = COMPARE_TO_HEAD.match(match["url"])
        if compare is None:
            raise RefusedError(
                f"cannot move the [{match['label']}] link in {CHANGELOG} on: expected "
                f"<repo>/compare/<tag>...HEAD, found {match['url']}"
            )
        base, previous = compare["base"], compare["start"]
        return [
            *lines[:index],
            f"[{match['label']}]: {base}v{version}...HEAD",
            f"[{version}]: {base}{previous}...v{version}",
            *lines[index + 1 :],
        ]
    return lines


def set_json_versions(text: str, fields: Sequence[tuple[str, ...]], version: str, name: str) -> str:
    """`text` with the string at each key path in `fields` set to `version`.

    The values are replaced in place rather than through json.dumps, so a file npm did not
    format is not restyled; parsing the result proves the replacements hit the right keys.
    Paths are matched in the order given, each after the previous one in the text.
    """
    expected: Any = json.loads(text)
    position = 0
    for path in fields:
        where = "".join(f"[{json.dumps(key)}]" for key in path)
        *parents, key = path
        try:
            holder = expected
            for parent in parents:
                holder = holder[parent]
            old = holder[key]
        except KeyError, TypeError:
            raise RefusedError(f"{name} has no {where}") from None
        if not isinstance(old, str):
            raise RefusedError(f"{name}: {where} is not a string")
        holder[key] = version
        match = re.compile(rf'"{re.escape(key)}"\s*:\s*"({re.escape(old)})"').search(text, position)
        if match is None:
            raise RefusedError(f"{name}: cannot find {where} = {old!r} in the text")
        text = text[: match.start(1)] + version + text[match.end(1) :]
        position = match.start(1) + len(version)
    if json.loads(text) != expected:
        raise RefusedError(f"{name}: its version fields are not laid out the way npm writes them")
    return text


def _read(root: Path, path: str) -> str:
    try:
        return (root / path).read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise RefusedError(f"{path} is missing") from None


def plan_release(root: Path, version: str, day: date) -> tuple[str, list[Change]]:
    """The current version and every file change a release of `version` makes."""
    try:
        parse_version(version)
    except RefusedError as refusal:
        hint = " (leave off the v: the tag adds it)" if version.startswith("v") else ""
        raise RefusedError(f"{refusal}{hint}") from None

    init_text = _read(root, INIT_FILE)
    found = INIT_VERSION.findall(init_text)
    if len(found) != 1:
        raise RefusedError(f"{INIT_FILE} needs exactly one __version__ line, found {len(found)}")
    current = found[0]

    package = _read(root, PACKAGE_JSON)
    lock = _read(root, PACKAGE_LOCK)
    changelog = _read(root, CHANGELOG)
    lock_fields = [("version",), ("packages", "", "version")]
    return current, [
        Change(INIT_FILE, init_text, INIT_VERSION.sub(f'__version__ = "{version}"', init_text)),
        Change(
            PACKAGE_JSON, package, set_json_versions(package, [("version",)], version, PACKAGE_JSON)
        ),
        Change(PACKAGE_LOCK, lock, set_json_versions(lock, lock_fields, version, PACKAGE_LOCK)),
        Change(CHANGELOG, changelog, release_changelog(changelog, version, day)),
    ]


def git(root: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name not in IDENTITY_ENV}
    if stdin is None:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    # Bytes in: in text mode Windows writes every "\n" to the pipe as "\r\n", and git's --stdin
    # readers then take "start\r" for an unknown command.
    raw = subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        input=stdin.encode("utf-8"),
        capture_output=True,
        check=False,
    )
    return subprocess.CompletedProcess(
        raw.args,
        raw.returncode,
        raw.stdout.decode("utf-8", "replace"),
        raw.stderr.decode("utf-8", "replace"),
    )


def local_identity(root: Path) -> tuple[str, str]:
    """user.name and user.email from this repository's own config, never from anywhere else.

    Privacy guard: the owner's global git identity is their real name, and this repository is
    published under a handle set in its own .git/config. A pushed release commit and tag cannot
    be taken back, so git's usual fallback to the global identity is refused outright.
    """
    values = []
    for key in ("user.name", "user.email"):
        result = git(root, "config", "--local", "--get", key)
        values.append(result.stdout.strip() if result.returncode == 0 else "")
    name, email = values
    if not name or not email:
        raise RefusedError(
            "no repository-level git identity: set both `git config --local user.name` and "
            "`git config --local user.email`; a release is never made with the global identity"
        )
    return name, email


def latest_release(root: Path) -> str | None:
    """The highest version among the v* tags, by the same rule a new version has to pass.

    A tag that does not parse (`vnext`, `v1.0.0+build`) was never made by this script and is not
    a release, so it is passed over rather than allowed to block or reorder one.
    """
    listed = git(root, "tag", "--list", "v*")
    if listed.returncode != 0:
        raise RefusedError(f"cannot list the tags: {listed.stderr.strip()}")
    releases: dict[str, VersionKey] = {}
    for tag in listed.stdout.split():
        try:
            releases[tag.removeprefix("v")] = parse_version(tag.removeprefix("v"))
        except RefusedError:
            continue
    return max(releases, key=releases.__getitem__, default=None)


def check_repository(root: Path, version: str, *, dry_run: bool) -> Repository:
    """Everything a release depends on outside the files; a dirty tree only refuses a real run."""
    inside = git(root, "rev-parse", "--is-inside-work-tree")
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise RefusedError(f"{root} is not a git working tree")
    # Valid SemVer can still be an invalid ref (`1.0.0-beta.1.lock`). Found only at `git tag`,
    # that would come after the files were written and committed: half a release.
    if git(root, "check-ref-format", f"refs/tags/v{version}").returncode != 0:
        raise RefusedError(f"git does not accept v{version} as a tag name (git check-ref-format)")
    if git(root, "rev-parse", "--quiet", "--verify", f"refs/tags/v{version}").returncode == 0:
        raise RefusedError(f"tag v{version} already exists")
    # A well-formed name that does not exist yet can still fail to be created: another ref
    # underneath it (refs/tags/v<version>/...), or a lock path past Windows' 260-character limit.
    # Rehearsing the creation in a ref transaction and aborting it finds those without leaving a
    # ref behind.
    rehearsal = git(
        root,
        "update-ref",
        "--stdin",
        stdin=f"start\ncreate refs/tags/v{version} HEAD\nprepare\nabort\n",
    )
    if rehearsal.returncode != 0:
        reason = rehearsal.stderr.strip().splitlines()[-1] if rehearsal.stderr.strip() else "?"
        raise RefusedError(f"git could not create tag v{version} here ({reason})")
    previous = latest_release(root)
    if previous is not None and parse_version(version) <= parse_version(previous):
        raise RefusedError(f"{version} is not greater than v{previous}, the highest release tag")
    identity = local_identity(root)
    dirty = bool(git(root, "status", "--porcelain").stdout.strip())
    if dirty and not dry_run:
        raise RefusedError(
            "the working tree is not clean (see git status): commit or set aside everything "
            "first, so that the release commit is the version bump and nothing else"
        )
    return Repository(identity, dirty, previous)


def _run(root: Path, command: str, *args: str, before: Sequence[str] = ()) -> str:
    result = git(root, *before, command, *args)
    if result.returncode != 0:
        raise GitError(f"git {command} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def release(root: Path, changes: Sequence[Change], version: str, identity: tuple[str, str]) -> str:
    """Write the changes, commit and tag them; the commit's hash."""
    for change in changes:
        atomic_write_bytes(root / change.path, change.after.encode("utf-8"))
    name, email = identity
    # Named on the command line because git would otherwise let an [include] or config.worktree,
    # which `--local` does not read, swap in another identity after the guard; git() has already
    # dropped the GIT_AUTHOR_* overrides.
    as_identity = ("-c", f"user.name={name}", "-c", f"user.email={email}")
    try:
        _run(root, "add", "--", *(change.path for change in changes))
        _run(root, "commit", "--quiet", "-m", f"chore(release): {version}", before=as_identity)
    except GitError as failure:
        raise GitError(f"{failure}\nthe files are changed and nothing is committed") from None
    commit = _run(root, "rev-parse", "HEAD")
    try:
        _run(
            root,
            "tag",
            "--annotate",
            f"v{version}",
            "-m",
            f"{APP_NAME} {version}",
            before=as_identity,
        )
    except GitError as failure:
        raise GitError(
            f"{failure}\nthe release commit {commit[:10]} exists and the tag does not"
        ) from None
    return commit


def unified_diff(change: Change) -> str:
    return "\n".join(
        difflib.unified_diff(
            change.before.splitlines(),
            change.after.splitlines(),
            f"a/{change.path}",
            f"b/{change.path}",
            lineterm="",
        )
    )


def main(argv: Sequence[str] | None = None, root: Path = ROOT, today: date | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bump_version.py",
        description="Bump the version, date the CHANGELOG section, commit and tag v<version>.",
    )
    parser.add_argument("version", help="the new version without the v, e.g. 1.0.0-beta.1")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the diffs, the commit and the tag, and change nothing",
    )
    args = parser.parse_args(argv)
    version: str = args.version

    try:
        current, changes = plan_release(root, version, today or date.today())
        repository = check_repository(root, version, dry_run=args.dry_run)
    except RefusedError as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        return 1

    name, email = repository.identity
    if args.dry_run:
        print(f"dry run: {current} -> {version}, nothing is written")
        for change in changes:
            print(unified_diff(change))
        print(f"commit: chore(release): {version}")
        print(f'tag:    v{version} (annotated: "{APP_NAME} {version}")')
        if repository.previous is None:
            print(
                "after:  no release tag here, so there is no earlier release to compare with "
                "and any valid version is accepted (git fetch --tags if that is wrong)"
            )
        else:
            print(f"after:  v{repository.previous}, the highest release tag here")
        print(f"as:     {name} <{email}>")
        if repository.dirty:
            print("note:   the working tree is not clean; the real run refuses until it is")
        return 0

    try:
        commit = release(root, changes, version, repository.identity)
    except GitError as failure:
        print(f"failed: {failure}", file=sys.stderr)
        return 1
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    print(f"{current} -> {version}: committed {commit[:10]} and tagged v{version} as {name}")
    print(f"publish with: git push --atomic origin {branch} v{version}")
    return 0


if __name__ == "__main__":
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        # A diff line can carry any character the CHANGELOG does; a cp1252 console cannot.
        reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.exit(main())
