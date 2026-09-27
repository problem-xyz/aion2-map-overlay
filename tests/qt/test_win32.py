"""The Windows version decision behind hiding the overlay from capture.

Only the decision is tested here. The ctypes calls themselves are left to a manual check:
a test cannot run on the old Windows build the check exists for.
"""

import sys

import pytest

from map_overlay.qt import win32
from map_overlay.qt.win32 import (
    CAPTURE_EXCLUSION_MIN_VERSION,
    supports_capture_exclusion,
    windows_version,
)


@pytest.mark.parametrize(
    ("version", "supported"),
    [
        ((10, 0, 19041), True),  # 2004, the first build that knows WDA_EXCLUDEFROMCAPTURE
        ((10, 0, 19045), True),  # 22H2
        ((10, 0, 26100), True),  # Windows 11 still reports itself as 10.0
        ((10, 0, 18363), False),  # 1909
        ((10, 0, 17763), False),  # 1809
        ((6, 3, 9600), False),  # 8.1
        ((6, 1, 7601), False),  # 7 SP1
    ],
)
def test_capture_exclusion_needs_windows_10_2004(
    version: tuple[int, int, int], supported: bool
) -> None:
    assert supports_capture_exclusion(version) is supported


def test_an_unknown_version_is_given_the_benefit_of_the_doubt() -> None:
    """Off Windows, or when RtlGetVersion failed: no warning about a Windows we cannot see."""
    assert supports_capture_exclusion(None) is True


def test_the_threshold_is_the_2004_build() -> None:
    assert CAPTURE_EXCLUSION_MIN_VERSION == (10, 0, 19041)


def test_off_windows_there_is_no_version(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(win32.sys, "platform", "linux")
    assert windows_version() is None


@pytest.mark.skipif(sys.platform != "win32", reason="RtlGetVersion exists only on Windows")
def test_on_windows_the_version_is_three_numbers() -> None:
    version = windows_version()
    assert version is not None
    assert len(version) == 3
    assert version[0] >= 10  # Python 3.14 itself does not install on anything older
