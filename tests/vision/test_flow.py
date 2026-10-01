"""FlowTracker: the shift it measures between two consecutive frames, and when it declines to.

Every pair of frames here is cut out of one larger picture, so the true displacement is exact and
known to the pixel -- `np.roll` would give the same number but put a wrap seam through the middle
of the tracked points.
"""

from collections.abc import Callable

import cv2
import numpy as np

from map_overlay.vision.flow import FlowTracker

# The displacement, and the tolerance the recovered shift must meet.
SHIFT_X, SHIFT_Y = 7, -3
TOLERANCE_PX = 0.5

WIDTH, HEIGHT = 512, 384
PAD = 64  # room around the crop, so both windows stay inside the source picture


def _pair(
    gradient: Callable[..., np.ndarray], dx: int = SHIFT_X, dy: int = SHIFT_Y
) -> tuple[np.ndarray, np.ndarray]:
    """Two grayscale frames, the second showing the same content moved by (dx, dy) pixels."""
    big = cv2.cvtColor(gradient(WIDTH + 2 * PAD, HEIGHT + 2 * PAD), cv2.COLOR_BGR2GRAY)
    prev = big[PAD : PAD + HEIGHT, PAD : PAD + WIDTH]
    # the window moves against the content: shifting it by (-dx, -dy) moves what it shows by
    # (+dx, +dy), which is the displacement the tracker has to report
    later = big[PAD - dy : PAD - dy + HEIGHT, PAD - dx : PAD - dx + WIDTH]
    return prev, later


def _flat() -> np.ndarray:
    return np.zeros((HEIGHT, WIDTH), np.uint8)


def _sparse(squares: int = 12) -> np.ndarray:
    """A flat field with a few bright blocks: real corners, but far fewer than the seed needs."""
    frame = _flat()
    for i in range(squares):
        top, left = 40 + (i // 4) * 60, 40 + (i % 4) * 60
        frame[top : top + 10, left : left + 10] = 255
    return frame


def test_the_shift_between_two_frames_is_recovered(gradient: Callable[..., np.ndarray]) -> None:
    prev, later = _pair(gradient)
    tracker = FlowTracker()
    tracker.step(prev)
    matrix = tracker.step(later)

    assert matrix is not None
    assert matrix.shape == (3, 3)
    assert abs(matrix[0, 2] - SHIFT_X) < TOLERANCE_PX
    assert abs(matrix[1, 2] - SHIFT_Y) < TOLERANCE_PX
    # a pure translation: no scale or rotation may be invented out of one
    assert np.allclose(matrix[:2, :2], np.eye(2), atol=1e-3)
    assert np.allclose(matrix[2], [0.0, 0.0, 1.0])


def test_the_first_frame_after_a_reset_only_seeds(gradient: Callable[..., np.ndarray]) -> None:
    """The docstring's contract: with nothing to compare against there is no shift to report."""
    tracker = FlowTracker()

    assert tracker.step(_pair(gradient)[0]) is None
    assert tracker.points > 0


def test_a_flat_frame_gives_no_transform() -> None:
    """An empty frame has no corners at all, so there is nothing to track from or to."""
    tracker = FlowTracker()

    assert tracker.step(_flat()) is None
    assert tracker.points == 0
    assert tracker.step(_flat()) is None
    assert tracker.points == 0


def test_points_are_dropped_when_the_next_frame_loses_them(
    gradient: Callable[..., np.ndarray],
) -> None:
    tracker = FlowTracker()
    tracker.step(_pair(gradient)[0])

    assert tracker.step(_flat()) is None
    assert tracker.points == 0


def test_a_frame_with_too_few_corners_is_not_seeded() -> None:
    """The seed keeps a point set only above `min_points`, which is `max_points // 5` (>= 12).

    The same frame decides both ways, so what is being tested is the threshold and not the
    picture: 12 corners is under the default tracker's 40 and exactly at a smaller one's 12.
    """
    sparse = _sparse(squares=12)

    default = FlowTracker()
    assert default.min_points == 40
    assert default.step(sparse) is None
    assert default.points == 0

    smaller = FlowTracker(max_points=60)
    assert smaller.min_points == 12
    smaller.step(sparse)
    assert smaller.points == 12


def test_the_point_budget_has_a_floor() -> None:
    assert (FlowTracker(max_points=5).max_points, FlowTracker(max_points=5).min_points) == (40, 12)
    assert (FlowTracker(max_points=300).max_points, FlowTracker(max_points=300).min_points) == (
        300,
        60,
    )


def test_reset_clears_the_points_and_the_previous_frame(
    gradient: Callable[..., np.ndarray],
) -> None:
    prev, later = _pair(gradient)
    tracker = FlowTracker()
    tracker.step(prev)
    assert tracker.step(later) is not None
    assert tracker.points > 0

    tracker.reset()

    assert tracker.points == 0
    # the sequence is broken, so the next frame is a first frame again and measures nothing --
    # it must not be compared against the frame from before the reset
    assert tracker.step(later) is None


def test_a_dropout_is_reseeded_from_the_previous_frame(
    gradient: Callable[..., np.ndarray],
) -> None:
    """Losing the point set costs one frame, not two: `step` seeds on the frame it kept.

    The set is emptied here by hand because the natural cause -- a frame the points cannot be
    found on -- also replaces the previous frame with that bad one.
    """
    big = cv2.cvtColor(gradient(WIDTH + 2 * PAD, HEIGHT + 2 * PAD), cv2.COLOR_BGR2GRAY)
    first = big[PAD : PAD + HEIGHT, PAD : PAD + WIDTH]
    second = big[PAD + 3 : PAD + 3 + HEIGHT, PAD - 7 : PAD - 7 + WIDTH]
    third = big[PAD + 6 : PAD + 6 + HEIGHT, PAD - 14 : PAD - 14 + WIDTH]

    tracker = FlowTracker()
    tracker.step(first)
    tracker.step(second)
    tracker._pts = None
    tracker.points = 0

    matrix = tracker.step(third)

    assert matrix is not None
    assert abs(matrix[0, 2] - SHIFT_X) < TOLERANCE_PX
    assert abs(matrix[1, 2] - SHIFT_Y) < TOLERANCE_PX
    assert tracker.points > 0


def test_a_frame_of_another_size_starts_over_instead_of_failing(
    gradient: Callable[..., np.ndarray],
) -> None:
    prev, later = _pair(gradient)
    tracker = FlowTracker()
    tracker.step(prev)

    # the map area was drawn again while running: the capture now hands frames of a new size
    assert tracker.step(later[: HEIGHT // 2, : WIDTH // 2].copy()) is None
    assert tracker.points > 0  # seeded on the new frame, ready for the next one
