"""Fail a release build whose tag and code disagree about the version.

    GITHUB_REF_NAME=v1.0.0-beta.1 uv run python scripts/check_version.py
    uv run python scripts/check_version.py v1.0.0-beta.1     # a ref named on the command line

The tag names the GitHub release and its place in the update feed; `__version__` is what the
exe, its properties dialog and the updater report. A release whose two halves disagree offers
users a version that calls itself something else once installed, and the updater then compares
against the wrong number. scripts/bump_version.py keeps them together; this catches a tag that
was made some other way.

This is for the release workflow, which runs on a tag push, where GitHub sets GITHUB_REF_NAME to
the tag. It is deliberately not in .github/workflows/ci.yml: that runs on pull requests and on
pushes to main, where GITHUB_REF_NAME is `<number>/merge` or `main`, so it would fail every run.
.github/workflows/release.yml runs it on every run: a tag push checks its own tag, and a manual
run, whose ref is a branch, passes `v` + the version it was asked to build as the argument.

Exit status: 0 when the tag matches, 1 when it does not, 2 when there is nothing to compare --
the variable is missing, or the ref is not a version tag.
"""

import argparse
import importlib.util
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from map_overlay import __version__

BUMP_VERSION = Path(__file__).resolve().parent / "bump_version.py"

MISMATCH = 1
NOTHING_TO_COMPARE = 2


def _load_bump_version() -> ModuleType:
    # One definition of a valid version, which bump_version.py takes from the build.
    spec = importlib.util.spec_from_file_location("bump_version", BUMP_VERSION)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {BUMP_VERSION}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bump_version = _load_bump_version()


def check(ref_name: str | None, version: str) -> tuple[int, str]:
    """The exit status and the message for a ref name against the code's version."""
    if not ref_name:
        return NOTHING_TO_COMPARE, (
            "GITHUB_REF_NAME is not set: this runs in the release workflow on a tag push, "
            "where GitHub sets it to the tag, e.g. v1.0.0-beta.1"
        )
    not_a_tag = (
        f"{ref_name!r} is not a version tag: expected v<MAJOR.MINOR.PATCH[-PRERELEASE]>, "
        "e.g. v1.0.0-beta.1"
    )
    if not ref_name.startswith("v"):
        return NOTHING_TO_COMPARE, not_a_tag
    try:
        bump_version.parse_version(ref_name.removeprefix("v"))
    except bump_version.RefusedError:
        return NOTHING_TO_COMPARE, not_a_tag
    if ref_name != f"v{version}":
        return MISMATCH, (
            f"tag {ref_name} does not match __version__ {version} in "
            "src/map_overlay/__init__.py: tag the commit scripts/bump_version.py made"
        )
    return 0, f"tag {ref_name} matches __version__ {version}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_version.py",
        description="Compare a tag, by default GITHUB_REF_NAME, with v + __version__.",
    )
    parser.add_argument("ref", nargs="?", help="the tag to compare, e.g. v1.0.0-beta.1")
    args = parser.parse_args(argv)
    ref = args.ref if args.ref is not None else os.environ.get("GITHUB_REF_NAME")
    status, message = check(ref, __version__)
    print(message, file=sys.stderr if status else sys.stdout)
    return status


if __name__ == "__main__":
    sys.exit(main())
