"""Share codes: the clipboard round trip, and the caps that make it safe to paste one.

A share code arrives from the clipboard, which means it arrives from anywhere, so the failures
matter as much as the round trip: every case asserts the share.* code the UI would translate.
"""

import base64
import zlib
from typing import Any

import pytest

from map_overlay.core.errors import ShareCodeError
from map_overlay.store.share import (
    MAX_DECODED_BYTES,
    SHARE_PREFIX,
    decode_share,
    encode_share,
)


def normalised_route() -> dict[str, Any]:
    """A route already in the shape validate_route returns, so it can be compared as it is."""
    return {
        "format": "map-overlay-route",
        "version": 1,
        "name": "Beluslan cafe run",
        "map": "beluslan",
        "mapSize": [4096, 4096],
        "markers": [
            {"x": 120.5, "y": 980.25, "text": "Start at the gate"},
            {"x": 1330.0, "y": 210.75, "text": "", "color": "#00ff88"},
        ],
        "style": {"color": "#f2b544", "width": 5},
    }


def bare_fifty_markers() -> dict[str, Any]:
    """Fifty points walked across a 4096 map, none of them carrying step text.

    Coordinates carry two decimals because that is what the app stores and what a click in the
    editor produces. A fixture on whole pixels encodes about 200 characters shorter, which would
    make the documented figure look better than any real route ever does.
    """
    markers: list[dict[str, float]] = []
    x, y = 1024.0, 980.0
    for i in range(50):
        x = round((x + 137 + (i * 29) % 61) % 4096 + i / 7, 2)
        y = round((y + 211 - (i * 17) % 53) % 4096 + i / 11, 2)
        markers.append({"x": x, "y": y})
    return {
        "format": "map-overlay-route",
        "version": 1,
        "name": "Gold route",
        "map": "elysea",
        "mapSize": [4096, 4096],
        "markers": markers,
        "style": {"color": "#f2b544", "width": 3},
    }


def test_a_code_decodes_back_to_the_document_it_was_made_from() -> None:
    doc = normalised_route()
    assert decode_share(encode_share(doc)) == doc


def test_whitespace_anywhere_inside_a_code_is_ignored() -> None:
    # A chat client wraps a long line; the code the user copies back still has to decode.
    code = encode_share(normalised_route())
    wrapped = f"  {code[:40]}\n{code[40:90]}\r\n\t{code[90:]}  "

    assert decode_share(wrapped) == decode_share(code)


@pytest.mark.parametrize("text", ["", "hello", "eNpFT8FO", "MO2.eNpFT8FO", "mo1.eNpFT8FO"])
def test_text_that_is_not_a_share_code_is_refused(text: str) -> None:
    with pytest.raises(ShareCodeError) as caught:
        decode_share(text)
    assert caught.value.code == "share.not_a_code"


def test_a_truncated_code_is_corrupt() -> None:
    code = encode_share(normalised_route())

    with pytest.raises(ShareCodeError) as caught:
        decode_share(code[:-24])

    assert caught.value.code == "share.corrupt"


def test_a_zlib_bomb_is_stopped_by_the_output_ceiling() -> None:
    # The point of the module. MAX_DECODED_BYTES is 1 MB, the documented ceiling for a decoded
    # share code; the payload has to exceed it, because a run of exactly
    # MAX_DECODED_BYTES bytes fits under the ceiling and fails later as unparsable JSON.
    zeros = zlib.compress(b"\0" * (4 * MAX_DECODED_BYTES), 9)
    code = SHARE_PREFIX + base64.urlsafe_b64encode(zeros).decode("ascii").rstrip("=")
    assert len(code) < 8000  # four megabytes of zeros arrive as a few kilobytes of text

    with pytest.raises(ShareCodeError) as caught:
        decode_share(code)

    assert caught.value.code == "share.too_large"
    assert caught.value.params == {"limit": MAX_DECODED_BYTES}


def test_fifty_markers_without_step_text_encode_to_a_chat_sized_code() -> None:
    """Guards the size the documentation quotes: about 800 characters bare.

    The bound is loose on purpose. The exact length moves with the coordinates, so pinning the
    measurement would turn an edit to this fixture into a failing test that says nothing. What
    is worth protecting is the order of magnitude the documentation promises -- a code that
    pastes into a chat message.
    """
    code = encode_share(bare_fifty_markers())

    assert len(code) < 900
