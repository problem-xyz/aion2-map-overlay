"""The tile pyramid: what a completed build leaves on disk, and what a cancelled one does not."""

from collections.abc import Callable
from pathlib import Path

import numpy as np

from map_overlay.store.images import imwrite
from map_overlay.store.tiles import build_tiles, detail_octaves, tiles_info


class StopAfter:
    """A `should_stop` that answers False a fixed number of times and True from then on.

    build_tiles asks before writing each tile, so `StopAfter(2)` cancels the build with exactly
    two tiles already on disk -- the half-built state the cleanup has to undo.
    """

    def __init__(self, calls: int) -> None:
        self._remaining = calls
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        if self._remaining > 0:
            self._remaining -= 1
            return False
        return True


def _map(tmp_path: Path, gradient: Callable[..., np.ndarray]) -> tuple[Path, Path]:
    """A 512x384 reference where resources live, and the map directory the app derives into.

    Two places on purpose: the reference is read-only and the directory does not exist until
    something is written into it, which is how the bundled maps are laid out.
    """
    reference = tmp_path / "assets" / "altgard" / "reference.png"
    imwrite(reference, gradient(512, 384))
    return tmp_path / "userdata" / "altgard", reference


def test_build_tiles_cuts_a_512x384_reference_into_five_tiles(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """zMax and the tile count follow the tile format: zMax = ceil(log2(max(w, h) / 256)).

    512x384 gives zMax 1, so the pyramid is a 2x2 level plus a 1x1 level: 4 + 1 = 5 files.
    """
    mdir, reference = _map(tmp_path, gradient)

    info = build_tiles(mdir, reference)

    assert info is not None
    assert info["zMax"] == 1
    assert info["tile"] == 256
    assert info["size"] == [512, 384]
    assert info["full"] == 512  # padded out to 256 * 2^zMax before cutting

    tiles_dir = mdir / "tiles"
    assert (tiles_dir / "done.json").exists()
    assert sorted(p.relative_to(tiles_dir).as_posix() for p in tiles_dir.rglob("*.jpg")) == [
        "0/0/0.jpg",
        "1/0/0.jpg",
        "1/0/1.jpg",
        "1/1/0.jpg",
        "1/1/1.jpg",
    ]


def test_tiles_info_reports_ready_after_a_completed_build(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    mdir, reference = _map(tmp_path, gradient)
    assert tiles_info(mdir) == {"ready": False, "zMax": 0, "tile": 256}

    build_tiles(mdir, reference)

    assert tiles_info(mdir) == {"ready": True, "zMax": 1, "tile": 256}
    assert tiles_info(mdir, (512, 384)) == {"ready": True, "zMax": 1, "tile": 256}


def test_a_pyramid_cut_from_an_image_of_another_size_is_not_ready(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """The regression: Altgard's image went from 8192 to 4096 pixels between versions, and the
    pyramid of the old one under the user's data directory was taken as the new map's."""
    mdir, reference = _map(tmp_path, gradient)
    build_tiles(mdir, reference)

    assert tiles_info(mdir, (1024, 768)) == {"ready": False, "zMax": 0, "tile": 256}
    # A marker from before the size was recorded is as untrustworthy as a wrong one.
    (mdir / "tiles" / "done.json").write_text('{"zMax": 1, "tile": 256}', encoding="utf-8")
    assert tiles_info(mdir, (512, 384)) == {"ready": False, "zMax": 0, "tile": 256}
    assert tiles_info(mdir) == {"ready": True, "zMax": 1, "tile": 256}


def test_a_pyramid_cut_from_a_detail_image_goes_past_the_map_s_own_top_level(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """The editor places routes in map pixels at zMax, so zMax stays the map's; zNative is how
    far the finer image lets it zoom before the tiles are only stretched."""
    mdir = tmp_path / "userdata" / "altgard"
    detail = tmp_path / "assets" / "altgard" / "detail.png"
    imwrite(detail, gradient(1024, 768))
    build_tiles(mdir, detail)

    assert tiles_info(mdir, (512, 384), (1024, 768)) == {
        "ready": True,
        "zMax": 1,
        "tile": 256,
        "zNative": 2,
    }
    # Taken for the reference's own pyramid, it would draw the map at twice the size of its routes.
    assert tiles_info(mdir, (512, 384)) == {"ready": False, "zMax": 0, "tile": 256}


def test_a_pyramid_cut_from_the_reference_is_not_ready_once_the_map_ships_a_detail_image(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """The update that brings a detail image has to cut every user's pyramid again."""
    mdir, reference = _map(tmp_path, gradient)
    build_tiles(mdir, reference)

    assert tiles_info(mdir, (512, 384), (1024, 768)) == {"ready": False, "zMax": 0, "tile": 256}


def test_detail_octaves_counts_doublings_in_both_directions_and_nothing_else() -> None:
    assert detail_octaves((512, 384), (1024, 768)) == 1
    assert detail_octaves((4096, 4096), (16384, 16384)) == 2
    assert detail_octaves((512, 384), (512, 384)) == 0, "the same size is no detail"
    assert detail_octaves((512, 384), (768, 576)) == 0, "one and a half times"
    assert detail_octaves((512, 384), (1024, 384)) == 0, "stretched one way"
    assert detail_octaves((512, 384), (256, 192)) == 0, "coarser"


def test_progress_is_reported_up_to_the_total_tile_count(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    mdir, reference = _map(tmp_path, gradient)
    seen: list[tuple[int, int]] = []

    def record(done: int, total: int) -> None:
        seen.append((done, total))

    build_tiles(mdir, reference, progress=record)

    # 5 is the same number the file listing above pins: 4 tiles at z=1 plus 1 at z=0.
    assert seen == [(4, 5), (5, 5)]


def test_a_cancelled_build_returns_none_and_removes_the_tiles_directory(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    """A partial pyramid must never be left behind: the editor would load it as a whole one."""
    mdir, reference = _map(tmp_path, gradient)
    should_stop = StopAfter(2)

    result = build_tiles(mdir, reference, should_stop=should_stop)

    assert result is None
    assert should_stop.calls == 3  # two tiles written, the third ask cancels
    # The return value alone would also be None if the two written tiles were still on disk.
    assert not (mdir / "tiles").exists()
    assert reference.exists()  # the source image is not collateral damage


def test_tiles_info_is_not_ready_after_a_cancelled_build(
    tmp_path: Path, gradient: Callable[..., np.ndarray]
) -> None:
    mdir, reference = _map(tmp_path, gradient)

    build_tiles(mdir, reference, should_stop=StopAfter(2))

    assert tiles_info(mdir) == {"ready": False, "zMax": 0, "tile": 256}
