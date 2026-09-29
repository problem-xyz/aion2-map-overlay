"""HDR frames: scRGB half floats back to the sRGB picture the tracker matches.

An HDR desktop is simulated the way Windows composes one: an sRGB image decoded to linear light
and multiplied by the SDR white level. Capture itself (Desktop Duplication) is not tested here.
"""

import numpy as np
import pytest

from map_overlay.vision.hdr import MIN_EXPOSURE, ScrgbToBgra


def _srgb_image(seed: int = 7, shape: tuple[int, int] = (120, 160)) -> np.ndarray:
    """A BGR uint8 image that reaches white, like a light map with white labels."""
    img = np.random.default_rng(seed).integers(0, 256, (*shape, 3), dtype=np.uint8)
    img[:4] = 255
    return img


def _compose(bgr: np.ndarray, sdr_white: float) -> np.ndarray:
    """RGBA half floats, as the HDR desktop holds an SDR picture at this white level."""
    x = bgr[..., ::-1].astype(np.float64) / 255.0
    linear = np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4) * sdr_white
    alpha = np.ones((*bgr.shape[:2], 1))
    return np.concatenate([linear, alpha], axis=2).astype(np.float16)


def _clip_to_8bit(rgba: np.ndarray) -> np.ndarray:
    """What an 8-bit capture of the same desktop returns: clipped at scRGB 1.0."""
    y = np.clip(rgba[..., :3].astype(np.float64), 0.0, 1.0)
    srgb = np.where(y <= 0.0031308, y * 12.92, 1.055 * y ** (1 / 2.4) - 0.055)
    return (srgb * 255 + 0.5).astype(np.uint8)[..., ::-1]


@pytest.mark.parametrize("sdr_white", [1.0, 2.5, 6.0, 12.5])
def test_an_sdr_picture_comes_back_at_any_sdr_brightness(sdr_white: float) -> None:
    bgr = _srgb_image()

    out = ScrgbToBgra()(_compose(bgr, sdr_white))

    assert out.dtype == np.uint8
    assert out.shape == (*bgr.shape[:2], 4)
    # half floats carry 11 significant bits, so a level or two of rounding is all that is lost
    assert np.abs(out[..., :3].astype(int) - bgr).max() <= 2
    assert (out[..., 3] == 255).all()


def test_the_8bit_capture_it_replaces_loses_the_light_half_of_the_picture() -> None:
    bgr = _srgb_image()
    rgba = _compose(bgr, 6.0)

    clipped = _clip_to_8bit(rgba)
    converted = ScrgbToBgra()(rgba)

    assert (clipped == 255).mean() > 0.5
    assert (converted[..., :3] == 255).mean() < 0.05


def test_the_exposure_holds_while_the_bright_end_moves_a_little() -> None:
    convert = ScrgbToBgra()
    bgr = _srgb_image()
    convert(_compose(bgr, 4.0))
    first = convert.exposure

    convert(_compose(bgr, 4.1))
    convert(_compose(bgr, 3.2))

    assert convert.exposure == first


@pytest.mark.parametrize("new_white", [6.0, 2.0])
def test_the_exposure_follows_a_large_change(new_white: float) -> None:
    convert = ScrgbToBgra()
    bgr = _srgb_image()
    convert(_compose(bgr, 4.0))

    out = convert(_compose(bgr, new_white))

    assert convert.exposure == pytest.approx(new_white, rel=0.01)
    assert np.abs(out[..., :3].astype(int) - bgr).max() <= 2


def test_a_black_frame_is_not_brightened_into_noise() -> None:
    rgba = np.zeros((40, 60, 4), np.float16)
    rgba[..., :3] = np.random.default_rng(1).random((40, 60, 3)) * 1e-3

    convert = ScrgbToBgra()
    out = convert(rgba)

    assert convert.exposure == MIN_EXPOSURE
    assert out[..., :3].max() < 20


def test_values_outside_the_picture_do_not_break_the_conversion() -> None:
    rgba = _compose(_srgb_image(), 2.5)
    rgba[0, 0, :3] = np.inf
    rgba[0, 1, :3] = np.nan
    rgba[0, 2, :3] = -0.5  # scRGB goes negative for colours outside sRGB

    out = ScrgbToBgra()(rgba)

    assert out[0, 0, :3].tolist() == [255, 255, 255]
    assert out[0, 1, :3].tolist() == [0, 0, 0]
    assert out[0, 2, :3].tolist() == [0, 0, 0]


def test_a_padded_mapped_surface_reads_the_same_as_a_packed_one() -> None:
    rgba = _compose(_srgb_image(), 2.5)
    h, w = rgba.shape[:2]
    # a mapped texture row is `pitch` bytes long, wider than the region it holds
    pitch = w * 8 + 64
    raw = np.zeros((h, pitch), np.uint8)
    raw[:, : w * 8] = rgba.view(np.uint8).reshape(h, w * 8)
    strided = raw[:, : w * 8].view(np.float16).reshape(h, w, 4)

    assert np.array_equal(ScrgbToBgra()(strided), ScrgbToBgra()(rgba))


@pytest.mark.parametrize("height", [1, 3, 5, 121])
def test_every_row_is_converted_whatever_the_height(height: int) -> None:
    # the rows are split into one band per thread, and the last band is the short one
    bgr = _srgb_image(shape=(height, 50))
    bgr[0] = 255

    convert = ScrgbToBgra()
    out = convert(_compose(bgr, 2.5))
    convert.close()

    assert np.abs(out[..., :3].astype(int) - bgr).max() <= 2
