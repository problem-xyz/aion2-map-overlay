"""Optical flow between consecutive frames, used between full re-detections."""

import cv2
import numpy as np


class FlowTracker:
    """Tracks how far the map moved between two neighbouring frames.

    Detection answers the question "where is the map on the reference", and that is expensive:
    tens of milliseconds. Optical flow answers the easier question "where did the picture go
    since the last frame", and that is 6-7 ms for a couple of hundred points. So the overlay
    position is carried by flow on every frame, and detection is used only now and then, to
    keep the error from piling up.

    The tracker holds the previous frame and its point set, so `step` must be fed consecutive
    frames from a single thread (the engine loop). Call `reset` whenever that sequence breaks --
    a new capture region, a rebuilt tracker -- or the next shift is measured against a frame
    that no longer has anything to do with the current one.
    """

    LK = {
        "winSize": (21, 21),
        "maxLevel": 3,
        "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 0.03),
    }

    def __init__(self, max_points=200) -> None:
        self.max_points = max(40, int(max_points))
        self.min_points = max(12, self.max_points // 5)
        self._prev = None
        self._pts = None
        self.points = 0

    def reset(self) -> None:
        self._prev = None
        self._pts = None
        self.points = 0

    def _seed(self, gray) -> None:
        """Collect fresh corners to track. Costs ~18 ms, so it runs only when the set runs low."""
        pts = cv2.goodFeaturesToTrack(
            gray, maxCorners=self.max_points, qualityLevel=0.01, minDistance=12, blockSize=7
        )
        self._pts = pts if pts is not None and len(pts) >= self.min_points else None
        self.points = 0 if self._pts is None else len(self._pts)

    def step(self, gray):
        """3x3 "previous frame -> this one", or None when the shift could not be measured.

        The first frame after a reset always returns None: it only seeds the point set.
        """
        prev = self._prev
        self._prev = gray
        if prev is None:
            self._seed(gray)
            return None
        if self._pts is None:
            # the points ran out on the previous step: seed them on the previous frame and track
            # straight through to this one, so a dropout costs one frame instead of two
            self._seed(prev)
        pts = self._pts
        if pts is None:
            return None

        # None lets OpenCV allocate the output points; its stubs type nextPts as required.
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(prev, gray, pts, None, **self.LK)  # pyright: ignore[reportCallIssue, reportArgumentType]
        good = status.ravel() == 1
        if int(good.sum()) < self.min_points:
            self._pts = None
            self.points = 0
            return None

        src, dst = pts[good], nxt[good]
        A, mask = cv2.estimateAffinePartial2D(
            src,
            dst,
            method=cv2.RANSAC,
            ransacReprojThreshold=2.0,
            maxIters=500,
            confidence=0.99,
            refineIters=5,
        )
        if A is None or mask is None or int(mask.sum()) < self.min_points:
            self._pts = None
            self.points = 0
            return None

        self._pts = dst[mask.ravel().astype(bool)].reshape(-1, 1, 2)
        self.points = len(self._pts)
        if self.points < self.max_points // 2:
            self._seed(gray)
        return np.vstack([A, [0.0, 0.0, 1.0]])
