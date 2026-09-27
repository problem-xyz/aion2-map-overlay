"""Image sizes read from file headers, which is how a bundled map is checked against its manifest
without decoding four thousand pixels a side at start-up.

Most headers here are built by hand and carry no pixel data at all, so the only way a test can
pass is by reading the header: a fallback decode would find nothing to decode.
"""

import struct
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import pytest

from map_overlay.store.images import header_size, image_size, imwrite

Header = Callable[[int, int], bytes]


def bmp_header(width: int, height: int, *, core: bool = False) -> bytes:
    """BITMAPFILEHEADER plus a BITMAPINFOHEADER, or the old 12-byte BITMAPCOREHEADER."""
    if core:
        info = struct.pack("<IHHHH", 12, width, height, 1, 24)
    else:
        info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, 0, 2835, 2835, 0, 0)
    return b"BM" + struct.pack("<IHHI", 14 + len(info), 0, 0, 14 + len(info)) + info


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_a_png_header_gives_its_size(tmp_path: Path, png_header: Header) -> None:
    assert header_size(_write(tmp_path, "a.png", png_header(16385, 7))) == (16385, 7)


def test_a_jpeg_header_gives_its_size(tmp_path: Path, jpeg_header: Header) -> None:
    # Width and height differ and neither fits in one byte, so a parser that is one byte off
    # -- the precision byte before the height -- cannot land on the right answer.
    assert header_size(_write(tmp_path, "a.jpg", jpeg_header(512, 384))) == (512, 384)


def test_a_real_jpeg_is_measured_correctly(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """The regression: the precision byte used to be read as the height's high byte.

    A 512x384 JPEG came back as 32770x2049, which the map size limit would have refused.
    """
    path = tmp_path / "map.jpg"
    imwrite(path, gradient(512, 384))

    assert header_size(path) == (512, 384)
    assert image_size(path) == (512, 384)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (bmp_header(640, 480), (640, 480)),
        (bmp_header(640, -480), (640, 480)),  # top-down rows: the sign is not the size
        (bmp_header(640, 480, core=True), (640, 480)),
    ],
)
def test_a_bmp_header_gives_its_size(
    tmp_path: Path, header: bytes, expected: tuple[int, int]
) -> None:
    assert header_size(_write(tmp_path, "a.bmp", header)) == expected


def test_a_real_bmp_is_measured_from_its_header(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    path = tmp_path / "map.bmp"
    imwrite(path, gradient(512, 384))

    assert header_size(path) == (512, 384)


@pytest.mark.parametrize(
    "params",
    [
        pytest.param([], id="lossy VP8"),
        pytest.param([cv2.IMWRITE_WEBP_QUALITY, 101], id="lossless VP8L"),
    ],
)
def test_a_real_webp_is_measured_from_its_header(
    tmp_path: Path, gradient: Callable[..., np.ndarray], params: list[int]
) -> None:
    """The bundled maps are WebP, and the registry checks their size against the manifest."""
    path = tmp_path / "map.webp"
    imwrite(path, gradient(64, 48), params)

    assert header_size(path) == (64, 48)


def test_an_extended_webp_header_gives_its_canvas_size(tmp_path: Path) -> None:
    """VP8X: the container the encoders reach for once there is alpha, an ICC profile or EXIF."""
    canvas = struct.pack("<I", 10) + bytes(4) + (16385 - 1).to_bytes(3, "little")
    canvas += (7 - 1).to_bytes(3, "little")
    data = b"RIFF" + struct.pack("<I", 4 + 8 + 10) + b"WEBP" + b"VP8X" + canvas

    assert header_size(_write(tmp_path, "a.webp", data)) == (16385, 7)


def test_a_format_without_a_shortcut_has_no_header_size(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    path = tmp_path / "map.tif"
    imwrite(path, gradient(64, 48))

    assert header_size(path) is None
    assert image_size(path) == (64, 48)  # which is what the decode fallback is for


@pytest.mark.parametrize("data", [b"", b"\x89PNG", b"\xff\xd8\xff\xc0\x00"])
def test_a_truncated_or_empty_header_has_no_size(tmp_path: Path, data: bytes) -> None:
    assert header_size(_write(tmp_path, "cut", data)) is None


def test_a_file_that_only_begins_with_bm_has_no_header_size(tmp_path: Path) -> None:
    # Read as a bitmap header, this text would claim a side of well over 16384 pixels and be
    # refused as too large rather than as the unreadable image it is.
    data = b"BMW maps of the old town, exported as text rather than as an image"

    assert header_size(_write(tmp_path, "notes.bmp", data)) is None


def test_a_missing_file_has_no_header_size(tmp_path: Path) -> None:
    assert header_size(tmp_path / "nope.png") is None
