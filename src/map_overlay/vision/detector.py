"""The worker thread that runs full re-detection off the engine loop.

Detection takes far longer than a frame, so it happens here and only corrects the binding that
optical flow carries in between. The job carries its own parameters: the engine used to mutate
the tracker's settings while this thread was reading them, which is the race T1 named.

A detection that raises is not fatal. A single bad frame, a reference file being rewritten
underneath us, an OpenCV edge case -- the loop treats those as a miss and keeps going. Only
repeated failure is worth stopping for, and that decision belongs to the engine, not here.
"""

import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any

import numpy as np

from map_overlay.vision.tracker import TrackerParams


@dataclass(frozen=True)
class DetectJob:
    """One frame plus the parameters it should be matched with."""

    frame: np.ndarray
    params: TrackerParams


@dataclass(frozen=True)
class DetectFailure:
    """One detection that raised, carried back to the engine thread.

    Delivered once: `Detector.error` clears it as it hands it over, so a caller that drops the
    value loses it. `message` is an exception string, not a sentence for the user -- the bridge
    wraps it in the `vision.detect_failed` code before anything reaches the UI.
    """

    message: str
    traceback: str


class Detector(threading.Thread):
    """Runs `Tracker.find` off the engine loop, one frame at a time.

    `set_tracker`, `submit`, `take`, `idle`, `error` and `stop` belong to the engine thread; the
    worker touches nothing but the job it was handed. That job is a frozen `DetectJob` carrying
    its own `TrackerParams`, so settings may change while a detection is in flight -- the result
    simply belongs to the parameters it was submitted with, never to a half-updated set.

    Only one job is ever in flight: `submit` refuses while the previous one is still running or
    its result has not been taken yet, and `stop` ends the thread for good.
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._cv = threading.Condition()
        self._tracker = None
        self._job: DetectJob | None = None
        self._result: tuple[Any, dict] | None = None
        self._error: DetectFailure | None = None
        self._busy = False
        self._stop = False

    def set_tracker(self, tracker) -> None:
        with self._cv:
            self._tracker = tracker
            self._job = None
            self._result = None
            self._busy = False

    def submit(self, job: DetectJob) -> bool:
        """Hand over a frame. False means the previous one is still being worked on."""
        with self._cv:
            if self._tracker is None or self._busy or self._result is not None:
                return False
            self._job = job
            self._busy = True
            self._cv.notify()
            return True

    def take(self):
        """(M, info) of the last detection, or None when nothing is ready."""
        with self._cv:
            result, self._result = self._result, None
            return result

    @property
    def idle(self) -> bool:
        return not self._busy

    def error(self) -> DetectFailure | None:
        with self._cv:
            err, self._error = self._error, None
            return err

    def stop(self) -> None:
        with self._cv:
            self._stop = True
            self._cv.notify_all()

    def run(self) -> None:
        while True:
            with self._cv:
                while self._job is None and not self._stop:
                    self._cv.wait(0.2)
                if self._stop:
                    return
                job, tracker = self._job, self._tracker
                self._job = None
            started = time.perf_counter()
            try:
                # The wait above ends with a job, and submit() takes none without a tracker.
                m, info = tracker.find(job.frame, job.params)  # pyright: ignore[reportOptionalMemberAccess]
            except Exception as e:  # noqa: BLE001 -- a bad frame must not kill the thread
                m, info = None, {}
                with self._cv:
                    self._error = DetectFailure(str(e), traceback.format_exc())
            info["detectMs"] = round((time.perf_counter() - started) * 1000, 1)
            with self._cv:
                self._result = (m, info)
                self._busy = False
