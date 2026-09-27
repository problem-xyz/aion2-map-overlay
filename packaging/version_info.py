"""Generate the Windows version resource that PyInstaller stamps into the exe.

`map_overlay.spec` names the result as `version="version_info.txt"`, so `scripts/build.ps1` runs
this first. The .txt is generated output and stays out of git.

Windows records the version twice over, and only one half can hold `beta`. The fixed-info block
is four 16-bit integers -- that is what the shell, an installer and an updater compare -- while
the string block beside it is free text. `1.0.0-beta.0` therefore ships as `(1, 0, 0, 0)` in the
numbers and in full in FileVersion, ProductVersion and Comments, so the properties dialog of a
prerelease never reads like the release it precedes.
"""

import logging
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from map_overlay import __version__
from map_overlay.core.appinfo import APP_NAME, ORG_NAME
from map_overlay.core.fileio import atomic_write_text

# PyInstaller is a dev-group dependency. The version rule below is also loaded by
# scripts/check_version.py, which has to run without it, so the import waits for the one
# function that builds the resource.
if TYPE_CHECKING:
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "version_info.txt"
LICENSE_FILE = HERE.parent / "LICENSE"

# SemVer 2.0.0's MAJOR.MINOR.PATCH[-PRERELEASE] and nothing looser, because
# scripts/bump_version.py writes and tags whatever passes here: no leading zeros in a number,
# no empty prerelease identifier, ASCII only ([0-9] rather than \d, which also matches
# fullwidth and Arabic-Indic digits). Build metadata (+...) is refused: SemVer ignores it for
# precedence, so an updater could not tell apart two releases that differ only by it.
_NUMBER = r"0|[1-9][0-9]*"
_IDENTIFIER = rf"(?:{_NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
SEMVER = re.compile(
    rf"({_NUMBER})\.({_NUMBER})\.({_NUMBER})(?:-({_IDENTIFIER}(?:\.{_IDENTIFIER})*))?", re.ASCII
)
UINT16_MAX = 0xFFFF

# Language 0x0409 (US English) over codepage 1200 (UTF-16). The string table's key and the
# Translation variable must name the same pair, or the shell finds no table to display.
LANG_CODEPAGE = "040904B0"
TRANSLATION = [0x0409, 1200]


def file_version(version: str) -> tuple[int, int, int, int]:
    """The four numbers of the fixed-info block, from a semver string.

    The fourth stays zero even for a prerelease: `beta.1` there would make the beta compare
    higher than the 1.0.0 it precedes, and the block has nowhere to say it is a prerelease.
    """
    match = SEMVER.fullmatch(version.strip())
    if match is None:
        raise ValueError(
            f"cannot parse version {version!r}; expected MAJOR.MINOR.PATCH[-PRERELEASE]"
        )
    major, minor, patch = (int(part) for part in match.group(1, 2, 3))
    # FixedFileInfo packs each number into 16 bits with a silent `& 0xffff`, so 1.70000.0 would
    # ship as 1.4464.0 rather than fail.
    if max(major, minor, patch) > UINT16_MAX:
        raise ValueError(f"version {version!r} does not fit the 16-bit fields Windows stores")
    return major, minor, patch, 0


def legal_copyright() -> str:
    """The copyright line, read from LICENSE so the holder is stated in exactly one place."""
    for line in LICENSE_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("Copyright "):
            return line.strip()
    raise ValueError(f"no copyright line in {LICENSE_FILE}")


def build_version_info(version: str) -> VSVersionInfo:
    """The resource for one version string."""
    from PyInstaller.utils.win32.versioninfo import (  # noqa: PLC0415 -- see TYPE_CHECKING above
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    numbers = file_version(version)
    strings = [
        StringStruct("CompanyName", ORG_NAME),
        StringStruct("FileDescription", APP_NAME),
        StringStruct("FileVersion", version),
        StringStruct("InternalName", APP_NAME),
        StringStruct("LegalCopyright", legal_copyright()),
        StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
        StringStruct("ProductName", APP_NAME),
        StringStruct("ProductVersion", version),
        # The one thing the numbers above cannot carry: which prerelease this build is.
        StringStruct("Comments", version),
    ]
    return VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[
            StringFileInfo([StringTable(LANG_CODEPAGE, strings)]),
            VarFileInfo([VarStruct("Translation", TRANSLATION)]),
        ],
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # str(VSVersionInfo) is the serialization PyInstaller itself reads back with eval, so the
    # format cannot drift away from the reader.
    atomic_write_text(OUTPUT, f"{build_version_info(__version__)}\n")
    log.info("wrote %s for version %s", OUTPUT, __version__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
