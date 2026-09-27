"""The tile pyramid the editor pans and zooms over.

A map image is 4096x4096 or larger, which no browser will render as one image, so it is cut
once into {z}/{x}/{y}.jpg levels and served from disk afterwards. What is cut is the map's
detail image when it ships one, so that the editor stays sharp zoomed in past the reference.
"""

import math
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2

from map_overlay.core.errors import MapError
from map_overlay.core.fileio import atomic_write_json, read_json_or_none
from map_overlay.store.images import imread, imwrite

TILE = 256


def tiles_info(
    mdir: Path | str,
    size: tuple[int, int] | None = None,
    detail: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """What is known about a map's tile pyramid: {"ready": bool, "zMax": int, "tile": int}.

    With `size`, a pyramid is ready only if it was cut from an image of that size. The map
    images ship with the app and can change between versions -- Altgard went from 8192 to
    4096 pixels -- while the pyramid under the user's data directory stays. Left as ready, the
    editor showed the top-left quarter of the old image with every object out of place.

    `detail` is the size of the finer image the pyramid is cut from instead, 2^k times `size`.
    zMax stays the level at which one tile pixel is one pixel of the map, because the editor
    places routes in map pixels at that level; the pyramid's own depth, k levels further, is
    reported as "zNative".
    """
    cut = detail or size
    done = Path(mdir) / "tiles" / "done.json"
    if done.exists():
        data = read_json_or_none(done)
        if isinstance(data, dict) and (cut is None or data.get("size") == list(cut)):
            try:
                z_native = int(data["zMax"])
                info = {"ready": True, "zMax": z_native, "tile": int(data.get("tile", TILE))}
            except KeyError, TypeError, ValueError:
                pass
            else:
                if detail and size:
                    info["zMax"] = z_native - detail_octaves(size, detail)
                    info["zNative"] = z_native
                return info
    return {"ready": False, "zMax": 0, "tile": TILE}


def detail_octaves(size: tuple[int, int], detail: tuple[int, int]) -> int:
    """k for a detail image 2^k times the map in both directions, or 0 when it is not one."""
    k = (detail[0] // size[0]).bit_length() - 1
    return k if k > 0 and detail == (size[0] << k, size[1] << k) else 0


def build_tiles(
    mdir: Path | str,
    reference: Path | str,
    *,
    tile: int = TILE,
    quality: int = 85,
    progress: Callable[[int, int], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> dict[str, Any] | None:
    """Cut the reference image into a {z}/{x}/{y}.jpg tile pyramid under mdir/tiles/.

    Level zMax is the map at its original resolution, and every level below it is half the
    size again: 341 tiles for a 4096x4096 map, 1365 for 8192x8192. Returns None when
    `should_stop` fired, leaving no partial pyramid behind.
    """
    mdir = Path(mdir)
    ref = imread(reference, cv2.IMREAD_COLOR)
    if ref is None:
        raise MapError("map.reference_missing", path=str(reference))
    h, w = ref.shape[:2]
    z_max = max(0, math.ceil(math.log2(max(w, h) / tile)))
    full = tile * (2**z_max)
    if (h, w) != (full, full):
        # Pad out to a square of 256*2^z; the smeared edge lies outside the map anyway.
        ref = cv2.copyMakeBorder(ref, 0, full - h, 0, full - w, cv2.BORDER_REPLICATE)

    tiles_dir = mdir / "tiles"
    shutil.rmtree(tiles_dir, ignore_errors=True)
    total = sum(4**z for z in range(z_max + 1))
    done = 0
    level = ref
    for z in range(z_max, -1, -1):
        n = 2**z
        for tx in range(n):
            col_dir = tiles_dir / str(z) / str(tx)
            col_dir.mkdir(parents=True, exist_ok=True)
            for ty in range(n):
                if should_stop is not None and should_stop():
                    shutil.rmtree(tiles_dir, ignore_errors=True)
                    return None
                cell = level[ty * tile : (ty + 1) * tile, tx * tile : (tx + 1) * tile]
                imwrite(col_dir / f"{ty}.jpg", cell, [cv2.IMWRITE_JPEG_QUALITY, quality])
                done += 1
        if progress is not None:
            progress(done, total)
        if z:
            level = cv2.resize(level, (n * tile // 2, n * tile // 2), interpolation=cv2.INTER_AREA)

    info = {"zMax": z_max, "tile": tile, "size": [w, h], "full": full}
    # Written last on purpose: its presence is what marks the pyramid as complete.
    atomic_write_json(tiles_dir / "done.json", info, indent=None)
    return info
