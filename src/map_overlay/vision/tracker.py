"""Matching the captured frame against the map reference."""

import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from map_overlay.store.images import imread
from map_overlay.vision.features import detect_tiled, make_detector

log = logging.getLogger(__name__)

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

    def __init__(
        self,
        reference_path,
        build: TrackerBuildParams,
        should_stop=None,
        *,
        coords_size=None,
        cache_dir=None,
    ) -> None:
        """`coords_size` (w, h) is the size the matrices are given in, when the image matched
        against is another: the map's 8192 px detail, whose points are brought down onto its 4096
        px reference, which the routes and everything else are drawn on. `cache_dir` keeps the
        image's points between runs, so that only the first start pays for finding them."""
        self.build = build
        self.path = reference_path
        self.coords_size = (
            None if coords_size is None else (int(coords_size[0]), int(coords_size[1]))
        )
        name = build.detector
        self.frame_detector, self.norm = make_detector(name, build.frame_features)
        found = _load_points(cache_dir, reference_path, build, self.coords_size)
        if found is None:
            found = self._detect(reference_path, build, should_stop, self.coords_size)
            _save_points(cache_dir, reference_path, build, self.coords_size, found)
        ref_pts, des_ref, image_size = found
        if des_ref is None or len(ref_pts) < 2 * MIN_REFERENCE_POINTS:
            raise ValueError("too few keypoints on the reference")
        w, h = self.coords_size or image_size
        self.ref_shape = (h, w)
        if (w, h) != image_size:
            ref_pts = ref_pts * np.array([w / image_size[0], h / image_size[1]], np.float32)
        self.ref_pts, self.des_ref = ref_pts, des_ref
        if self.norm == cv2.NORM_L2:
            # SIFT: kd-tree FLANN is several times faster than brute force at the same accuracy
            self.global_matcher = cv2.FlannBasedMatcher(
                {"algorithm": 1, "trees": 4}, {"checks": 64}
            )
            self.global_matcher.add([self.des_ref])
            self.global_matcher.train()
            # FLANN keeps its own float copy. SIFT's values are whole bytes, so ours can be a
            # quarter of the size (~33 MB less per map); the local search widens what it takes.
            small = des_ref.astype(np.uint8)
            if np.array_equal(small, des_ref):
                self.des_ref = small
        else:
            self.global_matcher = cv2.BFMatcher(self.norm, crossCheck=False)
        self.local_matcher = cv2.BFMatcher(self.norm, crossCheck=False)
        self._roi = None  # (x0, y0, x1, y1) in reference coordinates: where the map was last time

    @staticmethod
    def _detect(reference_path, build, should_stop, coords_size):
        # store.images.imread, not cv2.imread: OpenCV puts the path through the ANSI
        # codepage, so a map whose name cp1252 cannot spell never opens here.
        ref = imread(reference_path, cv2.IMREAD_GRAYSCALE)
        if ref is None:
            raise FileNotFoundError(reference_path)
        h, w = ref.shape[:2]
        # ref_features is for the map at its own size: a finer image of it gets as many points
        # to each patch of ground, or a close zoom would find as few on it as on the map.
        budget = build.ref_features
        if coords_size and budget > 0:
            budget = round(budget * (w * h) / (coords_size[0] * coords_size[1]))
        pts, des = detect_tiled(build.detector, ref, budget, should_stop=should_stop)
        return pts, des, (w, h)

    def _knn(self, des, subset):
        if subset is None:
            if self.norm == cv2.NORM_L2:
                return self.global_matcher.knnMatch(des, k=2)
            return self.global_matcher.knnMatch(des, self.des_ref, k=2)
        ref = self.des_ref[subset].astype(des.dtype, copy=False)  # SIFT's are kept as bytes
        return self.local_matcher.knnMatch(des, ref, k=2)

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
        return self.match(frame_features(self.frame_detector, frame_bgra, params), params)

    def match(self, features, params: TrackerParams):
        """find() on a frame whose keypoints frame_features() already found."""
        s = params
        kp, des, scale, (fh, fw), keypoints = features
        info = {"matches": 0, "inliers": 0, "reproj": None, "mode": "global"}
        # Near zero on a black or blank frame, which tells a capture problem from a map that
        # simply does not match.
        info["keypoints"] = keypoints
        if des is None or len(kp) < s.min_inliers:
            self._roi = None
            return None, info

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


def frame_features(detector, frame_bgra, params: TrackerParams):
    """The frame's keypoints and descriptors at params.detect_scale, and what match() needs."""
    scale = params.detect_scale
    if scale != 1.0:
        small = cv2.resize(frame_bgra, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    else:
        small = frame_bgra
    gray = cv2.cvtColor(small, cv2.COLOR_BGRA2GRAY)
    kp, des = detector.detectAndCompute(gray, None)
    return kp, des, scale, frame_bgra.shape[:2], len(kp)


# A map that misses this many detections in a row is let go, and every map is searched again: the
# player may have opened another one.
RELEASE_AFTER_MISSES = 8


class MapPicker:
    """Several maps, one of which is on the screen: which, it finds out itself.

    Until a map is found every detection is matched against all of them, and the one with the
    most inliers wins; from then on that map alone is matched, as a lone Tracker would be, until
    it has missed RELEASE_AFTER_MISSES detections in a row. The frame's keypoints are found once
    for all of them. `info["map"]` says which map a detection is of, by its index.

    It stands in for a Tracker wherever one is used: `path` and `coords_size` are the maps',
    in order, and `ref_shape` the map's in hand.
    """

    def __init__(self, trackers) -> None:
        self.trackers = list(trackers)
        first = self.trackers[0]
        self.build = first.build
        self.path = tuple(t.path for t in self.trackers)
        self.coords_size = tuple(t.coords_size for t in self.trackers)
        self.frame_detector = first.frame_detector
        self.active: int | None = None
        self._misses = 0

    @property
    def ref_shape(self):
        return self.trackers[self.active or 0].ref_shape

    def find(self, frame_bgra, params: TrackerParams):
        features = frame_features(self.frame_detector, frame_bgra, params)
        if self.active is not None:
            m, info = self.trackers[self.active].match(features, params)
            info["map"] = self.active
            if m is not None:
                self._misses = 0
                return m, info
            self._misses += 1
            if self._misses < RELEASE_AFTER_MISSES:
                return None, info
            self.active = None
        best = None
        info = {}
        for i, tracker in enumerate(self.trackers):
            m, info = tracker.match(features, params)
            if m is not None and (best is None or info["inliers"] > best[2]["inliers"]):
                best = (i, m, info)
        if best is None:
            return None, info
        self.active, m, info = best
        self._misses = 0
        info["map"] = self.active
        return m, info


# ------------------------------------------------------------------ the points, kept between runs


def _cache_file(cache_dir, reference_path, build, coords_size) -> Path | None:
    """Where the image's points are kept: named by what they were found with and in."""
    if cache_dir is None:
        return None
    image = Path(reference_path)
    try:
        # By content, not by place and date: an app update unpacks the same image into a new
        # folder with new dates, and keyed on those every update cost ~13 s per map to redo.
        content = hashlib.sha1(image.read_bytes()).hexdigest()
    except OSError:
        return None
    key = "|".join(
        map(
            str,
            (
                content,
                build.detector,
                build.ref_features,
                coords_size,
            ),
        )
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return Path(cache_dir) / f"points-{_image_name(reference_path)}-{digest}.npz"


def _image_name(reference_path) -> str:
    """The map's folder and the file: both maps call their detail detail.webp."""
    path = Path(reference_path)
    return f"{path.parent.name}-{path.stem}"


def _load_points(cache_dir, reference_path, build, coords_size):
    path = _cache_file(cache_dir, reference_path, build, coords_size)
    if path is None or not path.exists():
        return None
    try:
        with np.load(path) as data:
            pts = data["pts"].astype(np.float32)
            # SIFT's descriptors are whole numbers within a byte; ORB's are bytes already
            des = data["des"].astype(np.float32 if build.detector == "sift" else np.uint8)
            size = (int(data["size"][0]), int(data["size"][1]))
    except (OSError, KeyError, ValueError) as e:
        log.warning(
            "reference points in %s could not be read, finding them again: %s", path.name, e
        )
        return None
    return pts, des, size


def _save_points(cache_dir, reference_path, build, coords_size, found) -> None:
    pts, des, size = found
    path = _cache_file(cache_dir, reference_path, build, coords_size)
    if path is None or des is None:
        return
    small = des.astype(np.uint8)
    if not np.array_equal(small.astype(des.dtype), des):
        return  # not whole bytes after all: kept in memory only rather than stored changed
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written aside and renamed, so a run ended half-way leaves no torn file to read next time.
        part = path.with_name(path.name + ".part")
        with part.open("wb") as f:
            np.savez(f, pts=pts, des=small, size=np.array(size))
        part.replace(path)
        for old in path.parent.glob(f"points-{_image_name(reference_path)}-*.npz"):
            if old != path:
                old.unlink(missing_ok=True)
    except OSError as e:
        log.warning("reference points not kept in %s: %s", path.parent, e)
