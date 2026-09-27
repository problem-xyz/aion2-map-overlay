"""The version parser behind the build's Windows version resource.

packaging/ is a build directory rather than an importable package, and putting it on sys.path
for the whole suite would be a wide change for one script, so the file is loaded by path.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "version_info.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("packaging_version_info", SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


version_info = load_script()


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("1.0.0", (1, 0, 0, 0)),
        ("1.0.0-beta.0", (1, 0, 0, 0)),
        ("2.10.3-rc.1", (2, 10, 3, 0)),
        ("0.1.0-alpha", (0, 1, 0, 0)),
        # SemVer allows these, so the strict rule must too.
        ("0.0.0", (0, 0, 0, 0)),
        ("1.0.0-0", (1, 0, 0, 0)),
        ("1.0.0-0a.01a", (1, 0, 0, 0)),
        ("1.0.0--1", (1, 0, 0, 0)),
        ("1.0.0-x-y.7.z.92", (1, 0, 0, 0)),
    ],
)
def test_the_fixed_info_block_is_four_numbers_and_drops_the_prerelease(
    version: str, expected: tuple[int, int, int, int]
) -> None:
    """Windows stores four 16-bit integers; `beta.0` has to live in the string fields instead."""
    assert version_info.file_version(version) == expected


def test_a_prerelease_never_outranks_the_release_it_precedes() -> None:
    """Numbering a beta 1.0.0.1 would make the updater offer it over the finished 1.0.0."""
    assert version_info.file_version("1.0.0-beta.9") <= version_info.file_version("1.0.0")


@pytest.mark.parametrize(
    "version",
    ["", "1.0", "1", "1.0.0.0", "v1.0.0", "1.0.0-", "one.0.0", "1.0.0 beta", "1.0.0+win"],
)
def test_an_unparsable_version_is_refused_rather_than_shipped_as_zeros(version: str) -> None:
    """A silent 0.0.0.0 would reach the properties dialog of a release nobody could identify."""
    with pytest.raises(ValueError):
        version_info.file_version(version)


@pytest.mark.parametrize(
    "version",
    [
        "1.0.0-beta..1",
        "1.0.0-beta.",
        "1.0.0-.beta",
        "01.0.0",
        "1.01.0",
        "1.0.01",
        "00.0.0",
        "1.0.0-beta.01",
        "1.0.0-01",
        "\uff11.0.0",
        "\u0661.\u0660.\u0660",
        "1\u0660.0.0",
        "1.0.0-a\u0661",
        "1.0.0-b\u00e9ta",
        "1.0.0-beta+1",
    ],
    ids=[
        "empty identifier",
        "trailing dot",
        "leading dot",
        "leading zero in major",
        "leading zero in minor",
        "leading zero in patch",
        "double zero",
        "leading zero in a numeric identifier",
        "leading zero in the first identifier",
        "fullwidth digit",
        "arabic-indic digits",
        "arabic-indic digit after an ascii one",
        "arabic-indic digit in an identifier",
        "non-ascii letter",
        "build metadata after a prerelease",
    ],
)
def test_what_semver_forbids_is_refused(version: str) -> None:
    """SemVer 2.0.0 forbids each of these, and bump_version.py tags whatever passes here."""
    with pytest.raises(ValueError):
        version_info.file_version(version)


def test_a_number_too_large_for_a_16_bit_field_is_refused() -> None:
    """FixedFileInfo masks with & 0xffff, so 1.70000.0 would otherwise ship as 1.4464.0."""
    with pytest.raises(ValueError):
        version_info.file_version("1.70000.0")


@pytest.mark.parametrize("field", [0, 1, 2])
def test_the_16_bit_limit_is_exact(field: int) -> None:
    """65535 is the largest value a 16-bit field holds; one more must be refused, not wrapped."""
    largest = ["1", "0", "0"]
    largest[field] = "65535"
    assert version_info.file_version(".".join(largest))[field] == 65535
    too_large = ["1", "0", "0"]
    too_large[field] = "65536"
    with pytest.raises(ValueError):
        version_info.file_version(".".join(too_large))


def test_the_resource_still_builds_with_pyinstaller_imported_on_demand() -> None:
    """PyInstaller is imported inside build_version_info, so the build is where it must work."""
    resource = str(version_info.build_version_info("1.0.0-beta.1"))
    assert "filevers=(1, 0, 0, 0)" in resource
    assert "StringStruct('ProductVersion', '1.0.0-beta.1')" in resource
