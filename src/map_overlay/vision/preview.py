"""The debug preview image sent to the panel."""

import base64

import cv2
import numpy as np

from map_overlay.core.constants import PREVIEW_JPEG_QUALITY, PREVIEW_MAX_WIDTH

# The red that panel.preview.anchorHint and the README promise. OpenCV reads a colour as BGR:
# written the RGB way round, as (255, 120, 110), this same triple drew the crosshair blue-violet.
ANCHOR_BGR = (110, 120, 255)


def render_preview(frame_bgra, M, tracker, anchor=None):
    img = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
    if M is not None:
        h, w = tracker.ref_shape
        quad = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32).reshape(-1, 1, 2)
        pts = cv2.perspectiveTransform(quad, M).astype(np.int32)
        cv2.polylines(img, [pts], True, (80, 220, 120), 3, cv2.LINE_AA)
    if anchor is not None:
        # the crosshair marks where the engine believes the player is: when it sits away from
        # the player on screen, the captured region was drawn inaccurately
        ax, ay = round(anchor[0]), round(anchor[1])
        for color, thickness in (((20, 20, 20), 4), (ANCHOR_BGR, 2)):
            cv2.line(img, (ax - 16, ay), (ax + 16, ay), color, thickness, cv2.LINE_AA)
            cv2.line(img, (ax, ay - 16), (ax, ay + 16), color, thickness, cv2.LINE_AA)
        cv2.circle(img, (ax, ay), 20, ANCHOR_BGR, 2, cv2.LINE_AA)
    scale = min(1.0, PREVIEW_MAX_WIDTH / img.shape[1])
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_JPEG_QUALITY])
    return base64.b64encode(buf).decode("ascii") if ok else ""
