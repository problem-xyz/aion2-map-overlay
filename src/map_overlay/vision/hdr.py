"""Turning an HDR desktop frame into the 8-bit sRGB picture the tracker matches against.

With HDR on, Windows composes the desktop in linear scRGB half floats, where 1.0 is 80 nits and
SDR content is lifted to the "SDR content brightness" level -- 2.5 at 200 nits, more on a bright
monitor. An 8-bit capture clips that at 1.0, so everything above about a third of SDR white comes
out pure white; the map reference is a light image, and most of it goes. Capturing the half
floats and scaling them back down is the only way to keep that detail: once clipped, no contrast
correction afterwards can recover it.

The scale is the exposure: the frame's bright end is mapped to white. An SDR game never goes
above SDR white, so its brightest pixels land where they were before HDR composition and the
picture is the one the player sees; a game that renders in HDR keeps its highlights too, where a
fixed SDR white level would clip them.
"""

import numpy as np

# The share of pixels allowed to clip. A few specular glints or a white icon should not darken
# the whole frame, so the exposure follows a high percentile rather than the maximum.
EXPOSURE_PERCENTILE = 99.5
# Every 8th pixel in each direction: tens of thousands of samples on a map-sized region, enough
# for a stable percentile at a fraction of the cost of the full frame.
EXPOSURE_STRIDE = 8
# Never expose above scRGB 1.0, the level an 8-bit capture clips at. A dark or black frame would
# otherwise be brightened until its noise looked like texture.
MIN_EXPOSURE = 1.0
# Hysteresis: the exposure is changed only when the frame's bright end leaves this band around it.
# A steady exposure keeps consecutive frames alike, which is what optical flow relies on.
RAISE_ABOVE = 1.05
LOWER_BELOW = 0.7

_HALF_VALUES = np.arange(1 << 16, dtype=np.uint16).view(np.float16).astype(np.float32)


def _srgb_lut(exposure: float) -> np.ndarray:
    """uint8 sRGB value for every half-float bit pattern, at this exposure."""
    with np.errstate(invalid="ignore"):
        v = np.nan_to_num(_HALF_VALUES / exposure, nan=0.0, posinf=1.0, neginf=0.0)
    v = np.clip(v, 0.0, 1.0)
    srgb = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
    return (srgb * 255.0 + 0.5).astype(np.uint8)


class ScrgbToBgra:
    """Converts RGBA half-float scRGB frames to BGRA uint8, carrying the exposure between frames.

    Stateful for the exposure's hysteresis, so one instance serves one frame sequence, from one
    thread.
    """

    def __init__(self) -> None:
        self.exposure: float | None = None
        self._lut = np.zeros(1 << 16, np.uint8)

    def _bright_end(self, rgba: np.ndarray) -> float:
        sample = rgba[::EXPOSURE_STRIDE, ::EXPOSURE_STRIDE, :3].astype(np.float32).max(axis=2)
        sample = sample[np.isfinite(sample)]
        if sample.size == 0:
            return MIN_EXPOSURE
        return max(MIN_EXPOSURE, float(np.percentile(sample, EXPOSURE_PERCENTILE)))

    def _update_exposure(self, rgba: np.ndarray) -> None:
        peak = self._bright_end(rgba)
        e = self.exposure
        if e is None or peak > e * RAISE_ABOVE or peak < e * LOWER_BELOW:
            self.exposure = peak
            self._lut = _srgb_lut(peak)

    def __call__(self, rgba: np.ndarray) -> np.ndarray:
        """(H, W, 4) float16 RGBA, any strides -> a new (H, W, 4) uint8 BGRA frame."""
        self._update_exposure(rgba)
        bits = rgba.view(np.uint16)
        h, w = rgba.shape[:2]
        out = np.empty((h, w, 4), np.uint8)
        lut = self._lut
        # Indexing by the bit pattern is the whole conversion -- scale, clip and sRGB encoding --
        # in one table lookup per channel.
        out[..., 0] = lut[bits[..., 2]]
        out[..., 1] = lut[bits[..., 1]]
        out[..., 2] = lut[bits[..., 0]]
        out[..., 3] = 255
        return out
