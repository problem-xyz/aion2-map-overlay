"""Reading and writing image files, and the small colour helpers that go with them.

cv2.imread/imwrite cannot handle non-ASCII paths on Windows, so every read and write in the
project goes through this module instead of calling OpenCV directly.
"""

import base64
import re
import struct
from pathlib import Path
from typing import Any, BinaryIO

import cv2
import numpy as np

from map_overlay.core.errors import MapError
from map_overlay.core.fileio import atomic_write_bytes

_HEX_RE = re.compile(r"#[0-9a-fA-F]{6}")

# DIB header sizes after the 12-byte core header: OS/2 2.x (16, 64) and BITMAPINFOHEADER with
# its later versions (40, 52, 56, 108, 124). All keep 32-bit sides at the same offset.
_BMP_INFO_SIZES = frozenset({16, 40, 52, 56, 64, 108, 124})


def hex_color(value: Any) -> str | None:
    """A validated #rrggbb colour, or None.

    Empty strings and malformed values mean "no colour", not an error.
    """
    text = str(value or "")
    return text if _HEX_RE.fullmatch(text) else None


def _bgr(color: str) -> tuple[int, int, int]:
    """(B, G, R) for OpenCV. The input must already be a validated #rrggbb string."""
    return (int(color[5:7], 16), int(color[3:5], 16), int(color[1:3], 16))


def imread(path: Path | str, flags: int = cv2.IMREAD_COLOR) -> np.ndarray | None:
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
    except OSError:
        return None
    if data.size == 0:
        return None
    return cv2.imdecode(data, flags)


def encode_image(path: Path | str, img: np.ndarray, params: list[int] | None = None) -> bytes:
    """The bytes imwrite would put at `path`, in the format its suffix names, unwritten."""
    path = Path(path)
    ok, buf = cv2.imencode(path.suffix or ".png", img, params or [])
    if not ok:
        raise MapError("map.encode_failed", path=str(path))
    return buf.tobytes()


def imwrite(path: Path | str, img: np.ndarray, params: list[int] | None = None) -> None:
    atomic_write_bytes(path, encode_image(path, img, params))


def _webp_size(head: bytes) -> tuple[int, int] | None:
    """(w, h) from the first chunk of a WebP: VP8 (lossy), VP8L (lossless) or VP8X (extended)."""
    if len(head) < 30:
        return None
    chunk = head[12:16]
    if chunk == b"VP8 " and head[23:26] == b"\x9d\x01\x2a":
        w, h = struct.unpack("<HH", head[26:30])  # 14 bits of size and 2 of scaling, each
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L" and head[20] == 0x2F:
        bits = struct.unpack("<I", head[21:25])[0]  # two 14-bit fields, each one less
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":  # 24-bit canvas sides, each one less, after flags and reserved bytes
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    return None


def _bmp_size(head: bytes) -> tuple[int, int] | None:
    # BITMAPCOREHEADER (12 bytes) has 16-bit sides; every later header has signed 32-bit
    # ones, where a negative height only means the rows run top-down. Any other size is a
    # file that merely begins with "BM", and its "sides" are noise.
    info = struct.unpack("<I", head[14:18])[0]
    if info == 12:
        w, h = struct.unpack("<HH", head[18:22])
        return int(w), int(h)
    if info in _BMP_INFO_SIZES:
        w, h = struct.unpack("<ii", head[18:26])
        return abs(int(w)), abs(int(h))
    return None


def _jpeg_size(f: BinaryIO) -> tuple[int, int] | None:
    """Walk the segments after SOI to the first SOFn, which carries the size."""
    f.seek(2)
    while True:
        marker = f.read(2)
        if len(marker) < 2 or marker[0] != 0xFF:
            return None
        size = struct.unpack(">H", f.read(2))[0]
        if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
            # One byte of sample precision comes before the height.
            _, h, w = struct.unpack(">BHH", f.read(5))
            return int(w), int(h)
        f.seek(size - 2, 1)


def header_size(path: Path | str) -> tuple[int, int] | None:
    """(w, h) from a PNG, JPEG, BMP or WebP header without decoding the pixels, or None.

    None means this format has no shortcut here or the header could not be read; it says
    nothing about whether the image itself will decode.
    """
    try:
        with Path(path).open("rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
                w, h = struct.unpack(">II", head[16:24])
                return int(w), int(h)
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                return _webp_size(head)
            if head[:2] == b"BM":
                return _bmp_size(head)
            if head[:2] == b"\xff\xd8":
                return _jpeg_size(f)
    except OSError, struct.error:
        pass
    return None


def image_size(path: Path | str) -> tuple[int, int]:
    """Image size as (w, h), from the header wherever header_size can read one.

    Any other format falls back to a full decode; an unreadable file gives (0, 0).
    """
    size = header_size(path)
    if size is not None:
        return size
    img = imread(path, cv2.IMREAD_GRAYSCALE)  # unknown format: no header shortcut, decode it
    return (img.shape[1], img.shape[0]) if img is not None else (0, 0)


def data_url(img: np.ndarray, quality: int = 78) -> str:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii") if ok else ""
