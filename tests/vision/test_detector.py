"""Detector: the worker thread's survival contract, not the accuracy of what it computes.

Every test drives the worker through a stub tracker that signals from inside `find`, so a test
only proceeds once the thread has demonstrably picked the job up. Nothing here would pass with a
dead worker: the waits below end in an assertion that names what was never reached.
"""

import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
import pytest

from map_overlay.vision.detector import DetectFailure, DetectJob, Detector
from map_overlay.vision.tracker import TrackerParams

# Generous on purpose: a loaded CI box must not be able to fail these by being slow, and a broken
# worker fails them the moment the deadline passes rather than by timing out the whole run.
WAIT_S = 5.0

PARAMS = TrackerParams(
    ratio=0.75, reproj_thr=3.0, min_inliers=12, transform="affine", detect_scale=1.0
)

FAILURE_TEXT = "frame 7 is not a frame"


class _StubTracker:
    """Stands in for Tracker. `entered` fires inside `find`, on the worker thread.

    `hold`, when set, keeps `find` from returning until the test releases it, which is how a job
    is made to still be in flight at a known moment.
    """

    def __init__(self, *, raises: bool = False) -> None:
        self.entered = threading.Event()
        self.hold: threading.Event | None = None
        self.raises = raises
        self.calls = 0

    def find(self, frame: np.ndarray, params: TrackerParams) -> tuple[Any, dict]:
        self.calls += 1
        self.entered.set()
        if self.hold is not None:
            self.hold.wait(WAIT_S)
        if self.raises:
            raise RuntimeError(FAILURE_TEXT)
        return np.eye(3), {"mode": "global", "inliers": 42}


def _job() -> DetectJob:
    return DetectJob(frame=np.zeros((8, 8, 4), np.uint8), params=PARAMS)


def _wait_for(ready: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if ready():
            return
        time.sleep(0.005)
    raise AssertionError(f"waited {WAIT_S:g}s for {what} and it never happened")


@pytest.fixture
def detector() -> Iterator[Detector]:
    worker = Detector()
    worker.start()
    yield worker
    worker.stop()
    worker.join(WAIT_S)


def _run_failing_job(detector: Detector) -> _StubTracker:
    tracker = _StubTracker(raises=True)
    detector.set_tracker(tracker)
    assert detector.submit(_job())
    assert tracker.entered.wait(WAIT_S), "the worker never called find"
    _wait_for(lambda: detector.idle, "the worker to finish the failing job")
    return tracker


def test_a_detection_that_raises_does_not_kill_the_worker(detector: Detector) -> None:
    _run_failing_job(detector)

    assert detector.is_alive()
    failure = detector.error()
    assert isinstance(failure, DetectFailure)
    assert FAILURE_TEXT in failure.message
    assert "RuntimeError" in failure.traceback


def test_the_failure_is_handed_over_once(detector: Detector) -> None:
    """`error` clears as it returns, so an engine that drops the value has lost it."""
    _run_failing_job(detector)

    assert detector.error() is not None
    assert detector.error() is None


def test_submit_is_accepted_again_after_a_failure(detector: Detector) -> None:
    tracker = _run_failing_job(detector)
    detector.error()

    # Current behaviour: the failed detection left a result behind as well, and `submit` refuses
    # while one is waiting -- see test_a_failed_detection_also_publishes_a_result.
    assert detector.submit(_job()) is False
    assert detector.take() is not None

    tracker.raises = False
    tracker.entered.clear()
    assert detector.submit(_job()) is True
    assert tracker.entered.wait(WAIT_S), "the worker stopped taking jobs after the failure"
    _wait_for(lambda: detector.idle, "the worker to finish the second job")

    result = detector.take()
    assert result is not None
    matrix, info = result
    assert matrix is not None
    assert info["inliers"] == 42
    assert tracker.calls == 2


def test_a_failed_detection_also_publishes_a_result(detector: Detector) -> None:
    """Current behaviour, and a known defect: the failure and a result both come out of one job.

    `run` sets `_error` in the except branch and then falls through to publish `(None, info)`, so
    the engine sees a reported error *and* a detection that found nothing -- one failure counted
    as two misses. The case is filed; this test pins what the code does today so that fixing it
    shows up here as a failure to update, not as a silent behaviour change.
    """
    _run_failing_job(detector)
    assert detector.error() is not None

    result = detector.take()
    assert result is not None
    matrix, info = result
    assert matrix is None
    # nothing from the tracker survived, only the timing the worker adds afterwards
    assert list(info) == ["detectMs"]


def test_submit_is_refused_before_a_tracker_is_set(detector: Detector) -> None:
    assert detector.submit(_job()) is False


def test_only_one_job_is_in_flight_at_a_time(detector: Detector) -> None:
    tracker = _StubTracker()
    tracker.hold = threading.Event()
    detector.set_tracker(tracker)

    assert detector.submit(_job()) is True
    assert tracker.entered.wait(WAIT_S), "the worker never called find"
    assert detector.submit(_job()) is False
    assert not detector.idle

    tracker.hold.set()
    _wait_for(lambda: detector.idle, "the held job to finish")

    assert detector.take() is not None
    assert tracker.calls == 1


def test_stop_ends_the_worker_thread(detector: Detector) -> None:
    tracker = _StubTracker()
    detector.set_tracker(tracker)
    assert detector.submit(_job())
    # prove the thread is running before asking it to stop, or "not alive" would mean nothing
    assert tracker.entered.wait(WAIT_S), "the worker never called find"
    _wait_for(lambda: detector.idle, "the worker to finish the job")

    detector.stop()
    detector.join(1.0)  # the timeout Engine.run's finally block gives it

    assert not detector.is_alive()
