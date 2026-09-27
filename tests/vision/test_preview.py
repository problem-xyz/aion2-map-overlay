"""The preview picture the panel's "What detection sees" block shows.

The colour is read back off the encoded JPEG rather than compared with a constant: the defect
this pins was a correct-looking triple handed to OpenCV in the wrong channel order, and a test
that compared the constant with itself would have passed right through it.
"""

import base64

import cv2
import numpy as np

from map_overlay.vision.preview import render_preview


def _decode(jpeg_b64: str) -> np.ndarray:
    data = np.frombuffer(base64.b64decode(jpeg_b64), np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    assert img is not None, "the preview is not a decodable JPEG"
    return img


def test_the_anchor_crosshair_is_red_as_the_hint_says() -> None:
    frame = np.zeros((240, 320, 4), np.uint8)  # black, and narrow enough not to be scaled
    center = (160, 120)

    img = _decode(render_preview(frame, None, None, anchor=center))

    # The ring alone: the arms carry a dark outline, the ring is drawn in the one colour.
    ys, xs = np.ogrid[: img.shape[0], : img.shape[1]]
    distance = np.hypot(xs - center[0], ys - center[1])
    ring = img[(distance > 19) & (distance < 21)].mean(axis=0)
    # Hue, not channel ratios: the ring is a salmon red, and "red" is a statement about hue.
    # OpenCV's hue runs 0-180, and red is the wrap-around at both ends; blue-violet sits near 120.
    pixel = np.array([[ring]], dtype=np.uint8)
    hue, saturation, _ = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0, 0]
    assert hue < 10 or hue > 170, (ring, hue)
    assert saturation > 80, (ring, saturation)


def test_no_anchor_draws_no_crosshair() -> None:
    frame = np.zeros((240, 320, 4), np.uint8)

    img = _decode(render_preview(frame, None, None))

    assert img.max() < 16  # JPEG noise on black, nothing drawn
