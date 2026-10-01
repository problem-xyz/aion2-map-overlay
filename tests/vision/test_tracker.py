"""Tracker: recovering a known similarity warp, and the local search path.

The reference is generated here rather than loaded from a fixture image so that the transform
under test is known exactly: the frame is a crop of the reference put through a `cv2.warpAffine`
we wrote ourselves, so the matrix the tracker returns can be compared against the truth instead
of against a hand-measured guess.
"""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import pytest

from map_overlay.store.images import imwrite
from map_overlay.vision.tracker import Tracker, TrackerBuildParams, TrackerParams

REFERENCE_SIZE = 1024
CROP_SIZE = 300
CROP_ORIGIN = (362, 274)  # top-left of the crop in reference coordinates
WARP_SCALE = 1.3
WARP_ANGLE_DEG = 12.0

# Corner reprojection budget.
MAX_CORNER_ERROR_PX = 1.5

# SIFT only. Everything else is the shipped default from core/settings.py, so a regression here
# is a regression at the settings the user actually runs.
BUILD = TrackerBuildParams(detector="sift", ref_features=100_000, frame_features=2500)
PARAMS = TrackerParams(
    ratio=0.75, reproj_thr=4.0, min_inliers=20, transform="similarity", detect_scale=1.0
)


@dataclass(frozen=True)
class Scene:
    """A reference on disk plus one frame cut from it by a transform we know exactly."""

    reference_path: Path
    frame_bgra: np.ndarray
    expected: np.ndarray  # 3x3 reference -> frame, the answer the tracker has to find


def _reference_image(size: int = REFERENCE_SIZE) -> np.ndarray:
    """A BGR reference with texture a feature detector can actually hold on to.

    Scattered shapes, not a ramp: SIFT needs blobs and corners, and the Lowe ratio test throws
    away anything that repeats, so the placement is random (seeded) rather than a grid. The seed
    is fixed because this runs in CI -- the image has to be the same image on every machine.
    """
    rng = np.random.default_rng(20240517)
    img = np.full((size, size, 3), 48, np.uint8)

    circles = 900
    cx = rng.integers(0, size, circles)
    cy = rng.integers(0, size, circles)
    radius = rng.integers(4, 22, circles)
    color = rng.integers(30, 226, (circles, 3))
    for i in range(circles):
        cv2.circle(
            img,
            (int(cx[i]), int(cy[i])),
            int(radius[i]),
            (int(color[i, 0]), int(color[i, 1]), int(color[i, 2])),
            -1,
            cv2.LINE_AA,
        )

    boxes = 500
    bx = rng.integers(0, size, boxes)
    by = rng.integers(0, size, boxes)
    bw = rng.integers(6, 46, boxes)
    bh = rng.integers(6, 46, boxes)
    box_color = rng.integers(30, 226, (boxes, 3))
    for i in range(boxes):
        cv2.rectangle(
            img,
            (int(bx[i]), int(by[i])),
            (int(bx[i] + bw[i]), int(by[i] + bh[i])),
            (int(box_color[i, 0]), int(box_color[i, 1]), int(box_color[i, 2])),
            -1,
        )

    strokes = 400
    ax = rng.integers(0, size, strokes)
    ay = rng.integers(0, size, strokes)
    zx = ax + rng.integers(-60, 61, strokes)
    zy = ay + rng.integers(-60, 61, strokes)
    line_color = rng.integers(30, 226, (strokes, 3))
    for i in range(strokes):
        cv2.line(
            img,
            (int(ax[i]), int(ay[i])),
            (int(zx[i]), int(zy[i])),
            (int(line_color[i, 0]), int(line_color[i, 1]), int(line_color[i, 2])),
            1 + i % 3,
            cv2.LINE_AA,
        )

    # A touch of blur: hard aliased edges move by a pixel when the crop is resampled, and the
    # point of the test is the tracker's accuracy, not the drawing routine's.
    return cv2.GaussianBlur(img, (3, 3), 0.8)


def _warped_crop(reference: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cut CROP_SIZE**2 out of the reference and warp it by the known similarity.

    Returns the frame as BGRA -- `find` expects what the capture hands it -- and the 3x3
    reference -> frame matrix that produced it.
    """
    x0, y0 = CROP_ORIGIN
    crop = reference[y0 : y0 + CROP_SIZE, x0 : x0 + CROP_SIZE]

    half = CROP_SIZE / 2.0
    warp = cv2.getRotationMatrix2D((half, half), WARP_ANGLE_DEG, WARP_SCALE)
    corners = np.array(
        [[0, 0], [CROP_SIZE, 0], [CROP_SIZE, CROP_SIZE], [0, CROP_SIZE]], dtype=np.float32
    )
    moved = corners @ warp[:, :2].T + warp[:, 2]
    low, high = moved.min(axis=0), moved.max(axis=0)
    # Shift the result back into the frame, so the whole rotated crop is visible.
    warp[0, 2] -= float(low[0])
    warp[1, 2] -= float(low[1])
    frame_w = int(np.ceil(high[0] - low[0]))
    frame_h = int(np.ceil(high[1] - low[1]))

    frame = cv2.warpAffine(crop, warp, (frame_w, frame_h), flags=cv2.INTER_LINEAR)
    to_crop = np.array([[1.0, 0.0, -x0], [0.0, 1.0, -y0], [0.0, 0.0, 1.0]])
    expected = np.vstack([warp, [0.0, 0.0, 1.0]]) @ to_crop
    return cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA), expected


def _corner_errors(found: np.ndarray, expected: np.ndarray) -> np.ndarray:
    """Distance, per crop corner, between where `found` puts it and where the warp put it."""
    x0, y0 = CROP_ORIGIN
    corners = np.array(
        [
            [x0, y0],
            [x0 + CROP_SIZE, y0],
            [x0 + CROP_SIZE, y0 + CROP_SIZE],
            [x0, y0 + CROP_SIZE],
        ],
        dtype=np.float32,
    ).reshape(-1, 1, 2)
    got = cv2.perspectiveTransform(corners, found)
    want = cv2.perspectiveTransform(corners, expected)
    return np.linalg.norm(got - want, axis=2).ravel()


@pytest.fixture
def scene(tmp_path: Path) -> Scene:
    """A 1024x1024 reference written to disk, and one frame warped out of it."""
    reference = _reference_image()
    path = tmp_path / "reference.png"
    imwrite(path, reference)
    frame, expected = _warped_crop(reference)
    return Scene(reference_path=path, frame_bgra=frame, expected=expected)


def test_a_known_similarity_warp_is_recovered_to_within_a_pixel_and_a_half(scene: Scene) -> None:
    """The four crop corners reprojected through the returned matrix land on the warp's own.

    1.5 px is the budget; the corners are the honest place to measure it, because a small error in
    the recovered scale or rotation is largest there.
    """
    tracker = Tracker(str(scene.reference_path), BUILD)

    found, info = tracker.find(scene.frame_bgra, PARAMS)

    assert found is not None
    assert info["mode"] == "global"  # nothing placed yet, so the whole reference is searched
    assert info["inliers"] >= PARAMS.min_inliers
    errors = _corner_errors(found, scene.expected)
    assert errors.max() < MAX_CORNER_ERROR_PX, f"corner error {errors.max():.3f} px: {errors}"


def test_the_placed_map_makes_the_next_call_search_only_around_it(scene: Scene) -> None:
    """A successful find leaves an ROI behind, and the call after it matches inside that ROI.

    The mode is the whole point: the local path uses a subset of the reference keypoints, so it
    is both faster and less prone to a false match somewhere else on the map.
    """
    tracker = Tracker(str(scene.reference_path), BUILD)

    _, first = tracker.find(scene.frame_bgra, PARAMS)
    second_found, second = tracker.find(scene.frame_bgra, PARAMS)

    assert first["mode"] == "global"
    assert second["mode"] == "local"
    # `find` rewrites mode back to "global" when the local solve fails, so "local" surviving
    # here already means the local search produced the matrix -- this states it outright.
    assert second_found is not None
    assert _corner_errors(second_found, scene.expected).max() < MAX_CORNER_ERROR_PX


def test_a_map_named_in_a_non_ascii_alphabet_can_be_tracked(tmp_path: Path) -> None:
    """The reference read is the one place a Cyrillic map name used to stop the overlay.

    slugify keeps Unicode letters, so the map directory is named as the user typed it. Reading
    the reference with cv2.imread put that path through the ANSI codepage and returned None, and
    the user was told to pick the map again -- for a file every other part of the app could read.
    """
    map_dir = tmp_path / "Альтгард"  # allow-cyrillic: the non-ASCII name is the test
    map_dir.mkdir()
    reference = map_dir / "reference.png"
    imwrite(reference, _reference_image())
    assert reference.is_file(), "the fixture itself failed to write"

    tracker = Tracker(str(reference), BUILD)

    assert tracker.ref_shape == (REFERENCE_SIZE, REFERENCE_SIZE)


def test_a_finer_image_is_matched_and_answered_in_the_maps_own_pixels(
    scene: Scene, tmp_path: Path
) -> None:
    """The 8192 px detail is what a close zoom is found on; the routes are on the 4096 px map.

    So the matrix the tracker hands back is reference -> frame, whatever image it matched.
    """
    detail = cv2.resize(_reference_image(), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    path = tmp_path / "detail.png"
    imwrite(path, detail)

    tracker = Tracker(str(path), BUILD, coords_size=(REFERENCE_SIZE, REFERENCE_SIZE))
    found, _info = tracker.find(scene.frame_bgra, PARAMS)

    assert tracker.ref_shape == (REFERENCE_SIZE, REFERENCE_SIZE)
    assert found is not None
    assert _corner_errors(found, scene.expected).max() < MAX_CORNER_ERROR_PX


def test_the_points_are_kept_and_the_next_build_reads_them_back(
    scene: Scene, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    first = Tracker(str(scene.reference_path), BUILD, cache_dir=cache)
    assert len(list(cache.glob("points-*.npz"))) == 1

    def no_detection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the points were found again instead of read back")

    monkeypatch.setattr("map_overlay.vision.tracker.detect_tiled", no_detection)
    second = Tracker(str(scene.reference_path), BUILD, cache_dir=cache)

    assert np.array_equal(second.ref_pts, first.ref_pts)
    assert np.array_equal(second.des_ref, first.des_ref)
    found, _info = second.find(scene.frame_bgra, PARAMS)
    assert found is not None


def test_points_kept_for_another_version_of_the_image_are_not_used(
    scene: Scene, tmp_path: Path
) -> None:
    cache = tmp_path / "cache"
    Tracker(str(scene.reference_path), BUILD, cache_dir=cache)
    before = {p.name for p in cache.glob("points-*.npz")}

    # the map was updated: the same file, other pixels
    imwrite(scene.reference_path, cv2.flip(_reference_image(), 1))
    Tracker(str(scene.reference_path), BUILD, cache_dir=cache)
    after = {p.name for p in cache.glob("points-*.npz")}

    assert len(after) == 1
    assert after != before  # found again and kept under the new name, the old one gone
