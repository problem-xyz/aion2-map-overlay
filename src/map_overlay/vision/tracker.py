"""Matching the captured frame against the map reference."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from map_overlay.store.images import imread
from map_overlay.vision.features import detect_tiled, make_detector

# A reference with fewer keypoints than this cannot be matched at any setting.
MIN_REFERENCE_POINTS = 8


@dataclass(frozen=True)
class TrackerBuildParams:
    """What a Tracker is built from. Changing any of it means detecting the reference again."""

    detector: str
    ref_features: int
    frame_features: int

    @classmethod
    def from_mapping(cls, s: Mapping[str, Any]) -> TrackerBuildParams:
        return cls(
            detector=str(s["detector"]),
            ref_features=int(s["ref_features"]),
            frame_features=int(s["frame_features"]),
        )


@dataclass(frozen=True)
class TrackerParams:
    """What a Tracker reads per frame. Frozen, so the engine can swap it while a worker reads."""

    ratio: float
    reproj_thr: float
    min_inliers: int
    transform: str
    detect_scale: float

    @classmethod
    def from_mapping(cls, s: Mapping[str, Any]) -> TrackerParams:
        return cls(
            ratio=float(s["ratio"]),
            reproj_thr=float(s["reproj_thr"]),
            min_inliers=int(s["min_inliers"]),
            transform=str(s["transform"]),
            detect_scale=float(s["detect_scale"]),
        )


class Tracker:
    """Finds the reference map on a frame: a 3x3 reference -> frame matrix.

    Two search modes:
      * global -- the frame is matched against every keypoint of the reference (first frame, or
        after the map was lost);
      * local -- the map has already been placed, so only the keypoints around its previous
        position take part. That is several times faster and steadier: fewer foreign points,
        fewer false matches.

    Built on the engine thread, then handed to the detector thread, which is the only caller of
    `find`. `find` carries the ROI of the previous call, so two threads must not be inside it at
    once; everything that can change per frame arrives with the frame in `TrackerParams`, and
    nothing the tracker reads is mutated from outside while it runs.
    """

    def __init__(self, reference_path, build: TrackerBuildParams, should_stop=None) -> None:
        self.build = build
        self.path = reference_path
        # store.images.imread, not cv2.imread: OpenCV puts the path through the ANSI
        # codepage, so a map whose name cp1252 cannot spell never opens here.
        ref = imread(reference_path, cv2.IMREAD_GRAYSCALE)
        if ref is None:
            raise FileNotFoundError(reference_path)
        self.ref_shape = ref.shape[:2]  # (h, w)
        name = build.detector
        self.frame_detector, self.norm = make_detector(name, build.frame_features)
        ref_pts, des_ref = detect_tiled(name, ref, build.ref_features, should_stop=should_stop)
        if des_ref is None or len(ref_pts) < 2 * MIN_REFERENCE_POINTS:
            raise ValueError("too few keypoints on the reference")
        self.ref_pts, self.des_ref = ref_pts, des_ref
        if self.norm == cv2.NORM_L2:
            # SIFT: kd-tree FLANN is several times faster than brute force at the same accuracy
            self.global_matcher = cv2.FlannBasedMatcher(
                {"algorithm": 1, "trees": 4}, {"checks": 64}
            )
            self.global_matcher.add([self.des_ref])
            self.global_matcher.train()
        else:
            self.global_matcher = cv2.BFMatcher(self.norm, crossCheck=False)
        self.local_matcher = cv2.BFMatcher(self.norm, crossCheck=False)
        self._roi = None  # (x0, y0, x1, y1) in reference coordinates: where the map was last time

    def _knn(self, des, subset):
        if subset is None:
            if self.norm == cv2.NORM_L2:
                return self.global_matcher.knnMatch(des, k=2)
            return self.global_matcher.knnMatch(des, self.des_ref, k=2)
        return self.local_matcher.knnMatch(des, self.des_ref[subset], k=2)

    def _solve(self, kp, des, scale, subset, info, *, params):
        """Match, then fit the transform with RANSAC. subset = reference indices (None = all)."""
        s = params
        pairs = self._knn(des, subset)
        # Lowe ratio test: k=2 gives every match a runner-up, and only clearly better ones stay
        good = [p[0] for p in pairs if len(p) == 2 and p[0].distance < s.ratio * p[1].distance]
        info["matches"] = len(good)
        if len(good) < s.min_inliers:
            return None

        train_idx = np.array([m.trainIdx for m in good])
        if subset is not None:
            train_idx = subset[train_idx]
        src = self.ref_pts[train_idx].reshape(-1, 1, 2)
        dst = (
            np.array([kp[m.queryIdx].pt for m in good], dtype=np.float32).reshape(-1, 1, 2) / scale
        )

        thr = s.reproj_thr
        if s.transform == "homography":
            M, mask = cv2.findHomography(src, dst, cv2.RANSAC, thr, maxIters=3000, confidence=0.995)
            if M is None:
                return None
            M = M / M[2, 2]
            sc = float(np.sqrt(abs(np.linalg.det(M[:2, :2]))))
        else:
            A, mask = cv2.estimateAffinePartial2D(
                src,
                dst,
                method=cv2.RANSAC,
                ransacReprojThreshold=thr,
                maxIters=3000,
                confidence=0.995,
                refineIters=10,
            )
            if A is None:
                return None
            M = np.vstack([A, [0.0, 0.0, 1.0]])
            sc = float(np.hypot(A[0, 0], A[1, 0]))

        inl = int(mask.sum()) if mask is not None else 0
        info["inliers"] = inl
        if inl < s.min_inliers or not (0.05 < sc < 20.0):
            return None

        # mean reprojection error over the inliers -- the honest accuracy number for the stats
        m = mask.ravel().astype(bool)
        proj = cv2.perspectiveTransform(src[m], M)
        info["reproj"] = float(np.linalg.norm(proj - dst[m], axis=2).mean())
        return M

    def _update_roi(self, M, frame_w, frame_h, grow=0.5) -> None:
        """Where the frame lands on the reference, padded by `grow` on each side.

        The padding is the room the map has to move before the local search stops finding it.
        """
        corners = [[0, 0], [frame_w, 0], [frame_w, frame_h], [0, frame_h]]
        quad = np.array(corners, dtype=np.float32).reshape(-1, 1, 2)
        pts = cv2.perspectiveTransform(quad, np.linalg.inv(M)).reshape(-1, 2)
        x0, y0 = pts.min(axis=0)
        x1, y1 = pts.max(axis=0)
        mx, my = (x1 - x0) * grow, (y1 - y0) * grow
        self._roi = (x0 - mx, y0 - my, x1 + mx, y1 + my)

    def _roi_subset(self, min_inliers):
        if self._roi is None:
            return None
        x0, y0, x1, y1 = self._roi
        p = self.ref_pts
        idx = np.nonzero((p[:, 0] >= x0) & (p[:, 0] <= x1) & (p[:, 1] >= y0) & (p[:, 1] <= y1))[0]
        return idx if len(idx) >= 2 * min_inliers else None

    def find(self, frame_bgra, params: TrackerParams):
        """(M or None, info). params comes with the frame, so nothing here is shared state."""
        s = params
        scale = s.detect_scale
        info = {"matches": 0, "inliers": 0, "reproj": None, "mode": "global"}

        if scale != 1.0:
            small = cv2.resize(frame_bgra, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            small = frame_bgra
        gray = cv2.cvtColor(small, cv2.COLOR_BGRA2GRAY)

        kp, des = self.frame_detector.detectAndCompute(gray, None)
        if des is None or len(kp) < s.min_inliers:
            self._roi = None
            return None, info

        fh, fw = frame_bgra.shape[:2]
        subset = self._roi_subset(s.min_inliers)
        if subset is not None:
            info["mode"] = "local"
            M = self._solve(kp, des, scale, subset, info, params=s)
            if M is not None:
                self._update_roi(M, fw, fh)
                return M, info
            # nothing near the last position (a sharp pan or zoom) -- search the whole map
            info.update(matches=0, inliers=0, reproj=None, mode="global")

        M = self._solve(kp, des, scale, None, info, params=s)
        if M is not None:
            self._update_roi(M, fw, fh)
        else:
            self._roi = None
        return M, info
