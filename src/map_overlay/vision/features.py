"""Feature detection over a frame, tiled so that keypoints stay spread out."""

import math

import cv2
import numpy as np


def make_detector(name, nfeatures):
    if name == "orb":
        det = cv2.ORB.create(nfeatures=nfeatures, scaleFactor=1.2, nlevels=8, fastThreshold=10)
        return det, cv2.NORM_HAMMING
    return cv2.SIFT.create(nfeatures=nfeatures), cv2.NORM_L2


class CancelledError(Exception):
    """detect_tiled was asked to stop part-way through.

    Raised only because should_stop() went true, which here means the app is closing. Nothing
    partial comes back, and the caller abandons the build instead of reporting a failure.
    """


def detect_tiled(name, img, budget, *, tile=512, margin=48, should_stop=None):
    """Detect keypoints tile by tile, so that they cover the whole reference evenly.

    Run over the whole image with a limit of N, a detector keeps the N strongest points, and on
    a large reference (4096x4096) whole areas of the map can end up with none at all. budget is
    the total number of points (0 = no limit), split evenly between the tiles.
    Returns (points Nx2 float32, descriptors).

    should_stop is checked per tile. On a 8192x8192 reference this runs for many seconds, and
    without a way out the whole pass would have to finish before the app could close.
    """
    h, w = img.shape[:2]
    nx, ny = math.ceil(w / tile), math.ceil(h / tile)
    per_tile = 0 if budget <= 0 else max(100, math.ceil(budget / (nx * ny)))
    det, _ = make_detector(name, per_tile)
    pts, descs = [], []
    for ty in range(ny):
        for tx in range(nx):
            if should_stop is not None and should_stop():
                raise CancelledError
            x0, y0 = tx * tile, ty * tile
            x1, y1 = min(w, x0 + tile), min(h, y0 + tile)
            # a margin around the tile, so descriptors near its edges still see
            # their full neighbourhood
            ex0, ey0 = max(0, x0 - margin), max(0, y0 - margin)
            ex1, ey1 = min(w, x1 + margin), min(h, y1 + margin)
            kp, des = det.detectAndCompute(img[ey0:ey1, ex0:ex1], None)
            if des is None or len(kp) == 0:
                continue
            offset = np.array([ex0, ey0], dtype=np.float32)
            p = np.array([k.pt for k in kp], dtype=np.float32) + offset
            keep = (p[:, 0] >= x0) & (p[:, 0] < x1) & (p[:, 1] >= y0) & (p[:, 1] < y1)
            if keep.any():
                pts.append(p[keep])
                descs.append(des[keep])
    if not pts:
        return np.zeros((0, 2), np.float32), None
    return np.vstack(pts), np.vstack(descs)
